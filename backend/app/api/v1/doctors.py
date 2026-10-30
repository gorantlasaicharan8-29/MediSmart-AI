import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

try:
    from zoneinfo import ZoneInfo
    CLINIC_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.schemas.doctor import (
    DoctorDashboardStatsResponse,
    DoctorListResponse,
    DoctorNextAppointmentSummary,
    DoctorProfileSelfUpdate,
    DoctorResponse,
    DoctorSlot,
    DoctorSlotsDayResponse,
)

router = APIRouter()

# Standard 30-minute consultation clinic slots (09:00 - 17:00, lunch 13:00 - 14:00)
STANDARD_SLOTS = [
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30",
    "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30"
]


@router.get("", response_model=DoctorListResponse, summary="Search and list doctors")
async def list_doctors(
    search: Optional[str] = Query(None, description="Search by doctor name, specialty, or bio"),
    specialty: Optional[str] = Query(None, description="Filter by clinical specialty"),
    hospital_id: Optional[uuid.UUID] = Query(None, description="Filter by hospital affiliation"),
    city: Optional[str] = Query(None, description="Filter by hospital city"),
    credential_status: Optional[str] = Query(None, description="Filter by credential verification status"),
    available_only: bool = Query(False, description="Show only currently available doctors"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """Public doctor directory search with multi-parameter filtering and credential provenance."""
    query = select(Doctor).join(Doctor.user).join(Doctor.hospital)

    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.ilike(search_term),
                Doctor.specialty.ilike(search_term),
                Doctor.qualification.ilike(search_term),
                Doctor.bio.ilike(search_term),
                Hospital.name.ilike(search_term),
            )
        )

    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty.strip()}%"))

    if hospital_id:
        query = query.where(Doctor.hospital_id == hospital_id)

    if city:
        query = query.where(Hospital.city.ilike(f"%{city.strip()}%"))

    if credential_status:
        query = query.where(Doctor.credential_status == credential_status)

    if available_only:
        query = query.where(Doctor.is_available.is_(True))

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginate and load relationships
    offset = (page - 1) * page_size
    query = (
        query.options(
            selectinload(Doctor.user),
            selectinload(Doctor.hospital),
        )
        .order_by(Doctor.experience_years.desc(), User.full_name.asc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    doctors = result.scalars().all()

    return DoctorListResponse(
        items=list(doctors),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=DoctorResponse, summary="Get authenticated doctor's profile")
async def get_my_doctor_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
):
    """Retrieves the full professional doctor profile of the authenticated doctor."""
    query = (
        select(Doctor)
        .where(Doctor.user_id == current_user.id)
        .options(
            selectinload(Doctor.user),
            selectinload(Doctor.hospital),
        )
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found for this user account.",
        )

    return doctor


@router.patch("/me", response_model=DoctorResponse, summary="Update authenticated doctor's profile")
async def update_my_doctor_profile(
    payload: DoctorProfileSelfUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor")),
):
    """
    Allows the authenticated doctor to safely update their personal profile details.
    Protected attributes (credential_status, hospital affiliation) cannot be modified here.
    """
    query = (
        select(Doctor)
        .where(Doctor.user_id == current_user.id)
        .options(
            selectinload(Doctor.user),
            selectinload(Doctor.hospital),
        )
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found.",
        )

    if payload.bio is not None:
        doctor.bio = payload.bio.strip() if payload.bio else None
    if payload.is_available is not None:
        doctor.is_available = payload.is_available
    if payload.available_days is not None:
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        clean_days = [d.strip() for d in payload.available_days if d.strip() in valid_days]
        doctor.available_days = clean_days
    if payload.consultation_fee is not None:
        doctor.consultation_fee = payload.consultation_fee

    await db.commit()
    await db.refresh(doctor)
    return doctor


@router.get("/me/stats", response_model=DoctorDashboardStatsResponse, summary="Get doctor dashboard live statistics")
async def get_my_doctor_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor")),
):
    """
    Computes live dashboard summary statistics for the authenticated doctor:
    - Today's active appointments
    - Waiting patients count
    - Completed consultations count
    - Next upcoming appointment
    """
    # 1. Resolve Doctor profile
    query = (
        select(Doctor)
        .where(Doctor.user_id == current_user.id)
        .options(selectinload(Doctor.user))
    )
    res = await db.execute(query)
    doctor = res.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found.",
        )

    clinic_now = datetime.now(CLINIC_TZ)
    clinic_today = clinic_now.date()

    # 2. Count Today's Active Appointments
    appt_count_stmt = select(func.count(Appointment.id)).where(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == clinic_today,
        Appointment.status != "cancelled",
    )
    appt_count_res = await db.execute(appt_count_stmt)
    today_appointments = appt_count_res.scalar() or 0

    # 3. Queue statistics (waiting & completed today)
    waiting_stmt = select(func.count(QueueEntry.id)).where(
        QueueEntry.doctor_id == doctor.id,
        QueueEntry.queue_date == clinic_today,
        QueueEntry.status == "waiting",
    )
    waiting_res = await db.execute(waiting_stmt)
    waiting_patients = waiting_res.scalar() or 0

    completed_stmt = select(func.count(QueueEntry.id)).where(
        QueueEntry.doctor_id == doctor.id,
        QueueEntry.queue_date == clinic_today,
        QueueEntry.status == "completed",
    )
    completed_res = await db.execute(completed_stmt)
    completed_consultations = completed_res.scalar() or 0

    # 4. Next Upcoming Appointment
    next_appt_stmt = (
        select(Appointment)
        .where(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == clinic_today,
            Appointment.status.in_(["scheduled", "in_progress"]),
        )
        .options(selectinload(Appointment.patient))
        .order_by(Appointment.appointment_time.asc())
    )
    next_appt_res = await db.execute(next_appt_stmt)
    all_today_appts = next_appt_res.scalars().all()

    next_appointment_summary = None
    if all_today_appts:
        chosen = None
        for a in all_today_appts:
            if a.appointment_time >= clinic_now.time():
                chosen = a
                break
        if not chosen:
            chosen = all_today_appts[0]

        pat_name = chosen.patient.full_name if chosen.patient else "Patient"
        time_str = chosen.appointment_time.strftime("%I:%M %p")
        next_appointment_summary = DoctorNextAppointmentSummary(
            id=chosen.id,
            appointment_token=chosen.appointment_token,
            appointment_date=chosen.appointment_date,
            appointment_time=time_str,
            patient_name=pat_name,
            status=chosen.status,
        )

    doctor_name = doctor.user.full_name if doctor.user else "Doctor"

    return DoctorDashboardStatsResponse(
        doctor_id=doctor.id,
        doctor_name=doctor_name,
        today_appointments=today_appointments,
        waiting_patients=waiting_patients,
        completed_consultations=completed_consultations,
        next_appointment=next_appointment_summary,
        queue_date=clinic_today,
    )


@router.get("/{doctor_id}", response_model=DoctorResponse, summary="Get doctor profile by ID")
async def get_doctor_by_id(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint to fetch complete professional doctor profile with hospital affiliation."""
    query = (
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .options(
            selectinload(Doctor.user),
            selectinload(Doctor.hospital),
        )
    )
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    return doctor


@router.get("/{doctor_id}/slots", response_model=DoctorSlotsDayResponse, summary="Get doctor available consultation slots")
async def get_doctor_slots(
    doctor_id: uuid.UUID,
    slot_date: date = Query(..., alias="date", description="Date to check available slots (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """Calculates dynamic available 30-minute consultation slots on a given date."""
    clinic_now = datetime.now(CLINIC_TZ)
    clinic_today = clinic_now.date()

    if slot_date < clinic_today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot query consultation slots for past dates",
        )

    # Fetch doctor
    doc_query = select(Doctor).where(Doctor.id == doctor_id)
    doc_res = await db.execute(doc_query)
    doctor = doc_res.scalar_one_or_none()

    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    day_of_week = slot_date.strftime("%A")
    is_working_day = doctor.is_available and (day_of_week in doctor.available_days)

    # Query active booked appointments on this date
    appt_query = select(Appointment.appointment_time).where(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == slot_date,
        Appointment.status != "cancelled",
    )
    appt_res = await db.execute(appt_query)
    booked_times = {t.strftime("%H:%M") for t in appt_res.scalars().all()}

    # Compute slot availability
    now_time = clinic_now.strftime("%H:%M") if slot_date == clinic_today else None
    slots = []
    for slot_time in STANDARD_SLOTS:
        if not is_working_day:
            slot_status = "unavailable"
            available = False
        elif slot_time in booked_times:
            slot_status = "booked"
            available = False
        elif now_time and slot_time <= now_time:
            slot_status = "past"
            available = False
        else:
            slot_status = "available"
            available = True

        slots.append(DoctorSlot(time=slot_time, is_available=available, status=slot_status))

    return DoctorSlotsDayResponse(
        doctor_id=doctor_id,
        date=slot_date,
        day_of_week=day_of_week,
        is_working_day=is_working_day,
        slots=slots,
    )
