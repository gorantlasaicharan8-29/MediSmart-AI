import logging
import secrets
import uuid
from datetime import date, datetime, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Standard 30-minute consultation clinic slots (09:00 - 17:00, lunch 13:00 - 14:00)
ALLOWED_SLOT_TIMES = {
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30",
    "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30"
}


def _generate_appointment_token(appt_date: date) -> str:
    """Generates unique appointment token formatted as MS-YYYYMMDD-XXXX."""
    suffix = secrets.token_hex(2).upper()  # 4 hexadecimal characters
    return f"MS-{appt_date.strftime('%Y%m%d')}-{suffix}"


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a doctor consultation appointment",
)
async def book_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Creates a new appointment booking.
    - Enforces date validation (no past dates).
    - Enforces slot boundary validation (standard 30-min clinic slots).
    - Enforces doctor working days and availability.
    - Generates unique appointment tracking token (MS-YYYYMMDD-XXXX) with bounded retry.
    - Concurrency-safe: Database partial unique index guarantees no double bookings.
      Catches duplicate slot conflicts and translates safely to 409 Conflict.
    - Does not expose raw database exceptions to clients.
    """
    # 1. Date Validation
    if data.appointment_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book an appointment for a past date",
        )

    # 2. Slot Boundary Validation
    if data.appointment_time not in ALLOWED_SLOT_TIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Appointment time must be a valid 30-minute clinic slot between "
                "09:00 and 16:30 (excluding lunch 13:00-14:00)"
            ),
        )

    # Parse appointment time
    hour, minute = map(int, data.appointment_time.split(":"))
    appt_time_obj = time(hour, minute)

    # 3. Doctor Availability Validation
    doc_query = (
        select(Doctor)
        .where(Doctor.id == data.doctor_id)
        .options(selectinload(Doctor.hospital))
    )
    doc_res = await db.execute(doc_query)
    doctor = doc_res.scalar_one_or_none()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    if not doctor.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Doctor is currently unavailable for consultations",
        )

    day_of_week = data.appointment_date.strftime("%A")
    if day_of_week not in doctor.available_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Doctor does not take consultations on {day_of_week}s",
        )

    # 4. Transactional Booking with Bounded Token Collision Retry
    max_token_retries = 5
    for attempt in range(max_token_retries):
        token = _generate_appointment_token(data.appointment_date)

        # Check if token exists in session
        existing_token = await db.execute(
            select(Appointment.id).where(Appointment.appointment_token == token)
        )
        if existing_token.scalar_one_or_none():
            continue  # retry with fresh entropy

        new_appointment = Appointment(
            appointment_token=token,
            patient_id=current_user.id,
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            appointment_date=data.appointment_date,
            appointment_time=appt_time_obj,
            status="scheduled",
            notes=data.notes,
        )

        try:
            db.add(new_appointment)
            await db.flush()  # Trips PostgreSQL constraints immediately
            break  # Successfully inserted
        except IntegrityError as exc:
            await db.rollback()
            orig_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            logger.warning(
                f"IntegrityError encountered during appointment booking (attempt {attempt + 1}): {orig_msg}"
            )

            # Check if this was a slot collision from PostgreSQL partial unique index
            if "uq_active_doctor_slot" in orig_msg or "already exists" in orig_msg and "doctor_id" in orig_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This appointment time slot is already booked. Please choose another slot.",
                )

            # Check if it was a token collision
            if "appointment_token" in orig_msg:
                if attempt == max_token_retries - 1:
                    logger.error("Exhausted token collision retries during appointment booking.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Could not generate a unique appointment reference. Please try booking again.",
                    )
                continue  # Try next attempt with new token

            # For any other database integrity violation, fail safely without exposing raw SQL
            logger.error(f"Unexpected database integrity violation: {orig_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to complete booking due to a data constraint conflict.",
            )

    # Reload relationships for response
    full_appt_query = (
        select(Appointment)
        .where(Appointment.id == new_appointment.id)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.user),
            selectinload(Appointment.doctor).selectinload(Doctor.hospital),
            selectinload(Appointment.hospital),
        )
    )
    result = await db.execute(full_appt_query)
    created_appt = result.scalar_one()

    return created_appt


@router.get("", response_model=AppointmentListResponse, summary="List appointments with role isolation")
async def list_appointments(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by appointment status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List appointments with strict patient isolation.
    - Patients: Can ONLY view appointments where patient_id == current_user.id.
    - Doctors: View appointments where doctor_id == doctor profile ID.
    - Administrators: View all appointments.
    """
    query = select(Appointment)

    # Role-Based Data Isolation
    if current_user.role == "patient":
        query = query.where(Appointment.patient_id == current_user.id)
    elif current_user.role == "doctor":
        # Resolve doctor profile
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doc_id = doc_res.scalar_one_or_none()
        if not doc_id:
            return AppointmentListResponse(items=[], total=0, page=page, page_size=page_size)
        query = query.where(Appointment.doctor_id == doc_id)
    # Hospital admin or System admin can view all

    if status_filter:
        query = query.where(Appointment.status == status_filter)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = (
        query.options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.user),
            selectinload(Appointment.doctor).selectinload(Doctor.hospital),
            selectinload(Appointment.hospital),
        )
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    appointments = result.scalars().all()

    return AppointmentListResponse(
        items=list(appointments),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{appointment_id}", response_model=AppointmentResponse, summary="Get appointment by ID")
async def get_appointment_by_id(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves appointment details by ID.
    Strictly forbids cross-patient data access (403 Forbidden).
    """
    query = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.user),
            selectinload(Appointment.doctor).selectinload(Doctor.hospital),
            selectinload(Appointment.hospital),
        )
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Authorization Check
    if current_user.role == "patient" and appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only view your own appointments",
        )

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doc_id = doc_res.scalar_one_or_none()
        if appointment.doctor_id != doc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view your assigned appointments",
            )

    return appointment


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment transactionally",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    data: Optional[AppointmentCancelRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancels an active scheduled appointment.
    - Transactional row lock (`with_for_update()`) prevents race conditions.
    - Only the booking patient, assigned doctor, or administrator can cancel.
    - Patients cannot mark appointments as completed.
    - Updating status to 'cancelled' immediately frees the PostgreSQL partial unique index slot.
    """
    # Acquire pessimistic row lock
    query = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .with_for_update()
    )
    result = await db.execute(query)
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Ownership / Authorization Check
    is_owner = appointment.patient_id == current_user.id
    is_admin = current_user.role in ("hospital_admin", "system_admin")
    is_assigned_doctor = False

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doc_id = doc_res.scalar_one_or_none()
        if appointment.doctor_id == doc_id:
            is_assigned_doctor = True

    if not (is_owner or is_assigned_doctor or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only cancel your own appointments",
        )

    # Allowed status transition check
    if appointment.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel an appointment that is already {appointment.status}",
        )

    reason = data.cancellation_reason if data and data.cancellation_reason else "Cancelled by patient"
    appointment.status = "cancelled"
    appointment.cancellation_reason = reason

    # Reload relationships for response
    full_appt_query = (
        select(Appointment)
        .where(Appointment.id == appointment.id)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.user),
            selectinload(Appointment.doctor).selectinload(Doctor.hospital),
            selectinload(Appointment.hospital),
        )
    )
    res = await db.execute(full_appt_query)
    updated_appt = res.scalar_one()

    return updated_appt
