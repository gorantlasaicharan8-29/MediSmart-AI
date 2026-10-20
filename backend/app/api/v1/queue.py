import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.core.websocket import authenticate_websocket, queue_ws_manager
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User
from app.schemas.queue import (
    DoctorQueueItemResponse,
    DoctorQueueResponse,
    QueueActionRequest,
    QueueCheckInRequest,
    QueueEntryResponse,
    QueuePublicBoardResponse,
    QueuePublicItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    from zoneinfo import ZoneInfo
    CLINIC_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    from datetime import timedelta
    CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def _get_clinic_today():
    """Returns today's clinic date in Asia/Kolkata."""
    return datetime.now(CLINIC_TZ).date()


async def _verify_doctor_access(doctor_id: uuid.UUID, current_user: User, db: AsyncSession) -> Doctor:
    """
    Verifies that current_user has clinical management access to doctor_id.
    Doctors can only manage their own profile.
    Hospital admins can manage doctors belonging to their hospital.
    System admins have global access.
    """
    doc_res = await db.execute(
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .options(selectinload(Doctor.user), selectinload(Doctor.hospital))
    )
    doctor = doc_res.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    if current_user.role == "doctor":
        if doctor.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only manage your own queue",
            )
    elif current_user.role == "hospital_admin":
        admin_hosp = getattr(current_user, "hospital_id", None)
        if not admin_hosp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Hospital admin has no verified hospital affiliation configured.",
            )
        if doctor.hospital_id != admin_hosp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Doctor does not belong to your authorized hospital",
            )
    elif current_user.role != "system_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Clinical staff privileges required",
        )

    return doctor


@router.post(
    "/check-in",
    response_model=QueueEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Check in an appointment for today's clinic queue",
)
async def check_in_appointment(
    data: QueueCheckInRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Performs patient check-in for an appointment on the current clinic date (Asia/Kolkata).
    - Concurrency-safe: acquires PostgreSQL transaction-scoped advisory lock per doctor and date.
    - Allocates sequential daily token number.
    - Preserves database constraint safeguards.
    - Synchronizes appointment status and broadcasts live WebSocket update.
    """
    if not data.appointment_token and not data.appointment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either appointment_token or appointment_id must be provided",
        )

    # 1. Lookup Appointment
    appt_query = select(Appointment).options(
        selectinload(Appointment.doctor).selectinload(Doctor.user),
        selectinload(Appointment.doctor).selectinload(Doctor.hospital),
        selectinload(Appointment.patient),
        selectinload(Appointment.hospital),
    )
    if data.appointment_token:
        appt_query = appt_query.where(Appointment.appointment_token == data.appointment_token)
    else:
        appt_query = appt_query.where(Appointment.id == data.appointment_id)

    res = await db.execute(appt_query)
    appointment = res.scalar_one_or_none()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # 2. Authorization check
    if current_user.role == "patient" and appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only check in for your own appointment",
        )
    elif current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doc_id = doc_res.scalar_one_or_none()
        if appointment.doctor_id != doc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Doctors can only check in appointments for their own clinic",
            )
    elif current_user.role == "hospital_admin":
        admin_hosp = getattr(current_user, "hospital_id", None)
        if not admin_hosp or appointment.hospital_id != admin_hosp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Hospital admin can only check in appointments for their authorized hospital",
            )

    # 3. Clinic-Date check (Asia/Kolkata)
    clinic_today = _get_clinic_today()
    if appointment.appointment_date != clinic_today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Check-in is only available on the day of the appointment ({appointment.appointment_date}). "
                f"Current clinic date is {clinic_today}."
            ),
        )

    # 4. Status check
    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot check in for a cancelled appointment",
        )
    if appointment.status in ("in_progress", "completed", "no_show"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check in for an appointment that is already {appointment.status}",
        )

    # 5. Check if already checked in
    existing_entry_res = await db.execute(
        select(QueueEntry).where(QueueEntry.appointment_id == appointment.id)
    )
    if existing_entry_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This appointment has already been checked in to the queue",
        )

    # 6. Concurrency-Safe Daily Token Allocation with PostgreSQL Advisory Lock
    # Lock key: 2-argument (doctor_id, clinic_date) to serialize allocations per doctor and date
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:doc_id), hashtext(:c_date));"),
        {"doc_id": str(appointment.doctor_id), "c_date": str(clinic_today)},
    )

    # Query next sequential token number for this doctor on this clinic date
    max_token_res = await db.execute(
        select(func.coalesce(func.max(QueueEntry.token_number), 0)).where(
            QueueEntry.doctor_id == appointment.doctor_id,
            QueueEntry.queue_date == clinic_today,
        )
    )
    next_token = max_token_res.scalar_one() + 1

    # Query active waiting entries ahead
    waiting_count_res = await db.execute(
        select(func.count()).where(
            QueueEntry.doctor_id == appointment.doctor_id,
            QueueEntry.queue_date == clinic_today,
            QueueEntry.status == "waiting",
        )
    )
    waiting_ahead = waiting_count_res.scalar_one()
    initial_position = waiting_ahead + 1
    est_wait = waiting_ahead * 15

    # 7. Create Queue Entry inside same transaction and atomically update appointment status
    appointment.status = "checked_in"
    queue_entry = QueueEntry(
        id=uuid.uuid4(),
        appointment_id=appointment.id,
        hospital_id=appointment.hospital_id,
        doctor_id=appointment.doctor_id,
        patient_id=appointment.patient_id,
        queue_date=clinic_today,
        token_number=next_token,
        position=initial_position,
        status="waiting",
        estimated_wait_minutes=est_wait,
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(appointment)
    db.add(queue_entry)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(f"Integrity conflict during check-in: {exc}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Check-in conflict: a queue entry was already created for this appointment or token",
        )

    # 8. Broadcast real-time update
    await queue_ws_manager.broadcast_to_doctor(
        str(appointment.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(appointment.doctor_id),
            "action": "CHECKED_IN",
            "token_display": queue_entry.token_display,
            "token_number": queue_entry.token_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Format response
    doc_user = appointment.doctor.user if appointment.doctor else None
    doc_name = doc_user.full_name if doc_user else "Doctor"
    hosp_name = appointment.hospital.name if appointment.hospital else "Hospital"
    pat_name = appointment.patient.full_name if appointment.patient else "Patient"

    return QueueEntryResponse(
        id=queue_entry.id,
        appointment_id=queue_entry.appointment_id,
        hospital_id=queue_entry.hospital_id,
        doctor_id=queue_entry.doctor_id,
        patient_id=queue_entry.patient_id,
        queue_date=queue_entry.queue_date,
        token_number=queue_entry.token_number,
        token_display=queue_entry.token_display,
        position=queue_entry.position,
        status=queue_entry.status,
        estimated_wait_minutes=queue_entry.estimated_wait_minutes,
        checked_in_at=queue_entry.checked_in_at,
        called_at=queue_entry.called_at,
        completed_at=queue_entry.completed_at,
        patient_name=pat_name,
        doctor_name=doc_name,
        hospital_name=hosp_name,
        appointment_time=str(appointment.appointment_time),
        appointment_token=appointment.appointment_token,
    )


@router.get(
    "/my",
    response_model=QueueEntryResponse,
    summary="Get current patient's active queue entry and live position",
)
async def get_my_queue_entry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Retrieves the authenticated patient's current active queue entry for today.
    Calculates live position and wait time dynamically based on the current queue state.
    """
    clinic_today = _get_clinic_today()

    query = (
        select(QueueEntry)
        .where(
            QueueEntry.patient_id == current_user.id,
            QueueEntry.queue_date == clinic_today,
            QueueEntry.status.in_(["waiting", "in_consultation"]),
        )
        .options(
            selectinload(QueueEntry.appointment),
            selectinload(QueueEntry.doctor).selectinload(Doctor.user),
            selectinload(QueueEntry.hospital),
            selectinload(QueueEntry.patient),
        )
        .order_by(QueueEntry.created_at.desc())
        .limit(1)
    )
    res = await db.execute(query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active queue entry found for today",
        )

    # Dynamic Position and Estimated Wait Time
    if entry.status == "in_consultation":
        dyn_position = 0
        dyn_wait = 0
    else:
        ahead_count_res = await db.execute(
            select(func.count()).where(
                QueueEntry.doctor_id == entry.doctor_id,
                QueueEntry.queue_date == entry.queue_date,
                QueueEntry.status == "waiting",
                QueueEntry.token_number < entry.token_number,
            )
        )
        ahead_count = ahead_count_res.scalar_one()
        dyn_position = ahead_count + 1
        dyn_wait = ahead_count * 15

    doc_name = entry.doctor.user.full_name if (entry.doctor and entry.doctor.user) else "Doctor"
    hosp_name = entry.hospital.name if entry.hospital else "Hospital"
    pat_name = entry.patient.full_name if entry.patient else current_user.full_name
    appt_time = str(entry.appointment.appointment_time) if entry.appointment else None
    appt_tok = entry.appointment.appointment_token if entry.appointment else None

    return QueueEntryResponse(
        id=entry.id,
        appointment_id=entry.appointment_id,
        hospital_id=entry.hospital_id,
        doctor_id=entry.doctor_id,
        patient_id=entry.patient_id,
        queue_date=entry.queue_date,
        token_number=entry.token_number,
        token_display=entry.token_display,
        position=dyn_position,
        status=entry.status,
        estimated_wait_minutes=dyn_wait,
        checked_in_at=entry.checked_in_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
        patient_name=pat_name,
        doctor_name=doc_name,
        hospital_name=hosp_name,
        appointment_time=appt_time,
        appointment_token=appt_tok,
    )


@router.get(
    "/doctor/{doctor_id}/public-board",
    response_model=QueuePublicBoardResponse,
    summary="Get public waiting room queue monitor (Zero PII)",
)
async def get_doctor_public_board(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Publicly accessible endpoint for clinic waiting room display monitors.
    Returns anonymized tokens, positions, and wait times.
    Contains strictly ZERO patient PII (no names, emails, phones, or notes).
    """
    doc_res = await db.execute(
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .options(selectinload(Doctor.user), selectinload(Doctor.hospital))
    )
    doctor = doc_res.scalar_one_or_none()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    clinic_today = _get_clinic_today()

    entries_res = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.queue_date == clinic_today,
            QueueEntry.status.in_(["waiting", "in_consultation"]),
        )
        .order_by(QueueEntry.token_number.asc())
    )
    entries = entries_res.scalars().all()

    current_consult = None
    waiting_items = []
    waiting_idx = 0

    for e in entries:
        if e.status == "in_consultation" and current_consult is None:
            current_consult = QueuePublicItem(
                token_display=e.token_display,
                token_number=e.token_number,
                position=0,
                status=e.status,
                estimated_wait_minutes=0,
            )
        elif e.status == "waiting":
            waiting_idx += 1
            waiting_items.append(
                QueuePublicItem(
                    token_display=e.token_display,
                    token_number=e.token_number,
                    position=waiting_idx,
                    status=e.status,
                    estimated_wait_minutes=(waiting_idx - 1) * 15,
                )
            )

    doc_name = doctor.user.full_name if doctor.user else "Doctor"
    hosp_name = doctor.hospital.name if doctor.hospital else "Hospital"

    return QueuePublicBoardResponse(
        doctor_id=doctor.id,
        doctor_name=doc_name,
        specialty=doctor.specialty,
        hospital_name=hosp_name,
        queue_date=clinic_today,
        current_consultation=current_consult,
        waiting_list=waiting_items,
        total_waiting=len(waiting_items),
    )


@router.get(
    "/doctor/{doctor_id}",
    response_model=DoctorQueueResponse,
    summary="Get full clinical queue for authorized doctor or staff",
)
async def get_doctor_clinical_queue(
    doctor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Authenticated clinical queue view for assigned doctor and authorized hospital administrators.
    Displays patient names, appointment details, and full lifecycle controls.
    """
    doctor = await _verify_doctor_access(doctor_id, current_user, db)
    clinic_today = _get_clinic_today()

    entries_res = await db.execute(
        select(QueueEntry)
        .where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.queue_date == clinic_today,
        )
        .options(
            selectinload(QueueEntry.patient),
            selectinload(QueueEntry.appointment),
        )
        .order_by(QueueEntry.token_number.asc())
    )
    entries = entries_res.scalars().all()

    current_consult = None
    waiting_items = []
    total_completed = 0
    total_skipped = 0
    waiting_idx = 0

    for e in entries:
        pat_name = e.patient.full_name if e.patient else "Patient"
        pat_email = e.patient.email if e.patient else None
        pat_phone = e.patient.phone if e.patient else None
        appt_tok = e.appointment.appointment_token if e.appointment else ""
        appt_time = str(e.appointment.appointment_time) if e.appointment else ""

        if e.status == "in_consultation" and current_consult is None:
            current_consult = DoctorQueueItemResponse(
                id=e.id,
                token_number=e.token_number,
                token_display=e.token_display,
                position=0,
                status=e.status,
                patient_id=e.patient_id,
                patient_name=pat_name,
                patient_email=pat_email,
                patient_phone=pat_phone,
                appointment_id=e.appointment_id,
                appointment_token=appt_tok,
                appointment_time=appt_time,
                checked_in_at=e.checked_in_at,
                called_at=e.called_at,
                completed_at=e.completed_at,
                notes=e.notes,
            )
        elif e.status == "waiting":
            waiting_idx += 1
            waiting_items.append(
                DoctorQueueItemResponse(
                    id=e.id,
                    token_number=e.token_number,
                    token_display=e.token_display,
                    position=waiting_idx,
                    status=e.status,
                    patient_id=e.patient_id,
                    patient_name=pat_name,
                    patient_email=pat_email,
                    patient_phone=pat_phone,
                    appointment_id=e.appointment_id,
                    appointment_token=appt_tok,
                    appointment_time=appt_time,
                    checked_in_at=e.checked_in_at,
                    called_at=e.called_at,
                    completed_at=e.completed_at,
                    notes=e.notes,
                )
            )
        elif e.status == "completed":
            total_completed += 1
        elif e.status == "skipped":
            total_skipped += 1

    doc_name = doctor.user.full_name if doctor.user else "Doctor"
    hosp_name = doctor.hospital.name if doctor.hospital else "Hospital"

    return DoctorQueueResponse(
        doctor_id=doctor.id,
        doctor_name=doc_name,
        specialty=doctor.specialty,
        hospital_id=doctor.hospital_id,
        hospital_name=hosp_name,
        queue_date=clinic_today,
        current_consultation=current_consult,
        waiting_list=waiting_items,
        total_waiting=len(waiting_items),
        total_completed=total_completed,
        total_skipped=total_skipped,
    )


@router.post(
    "/{entry_id}/call",
    response_model=DoctorQueueItemResponse,
    summary="Call a patient into consultation (concurrency-protected)",
)
async def call_patient(
    entry_id: uuid.UUID,
    data: Optional[QueueActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Calls a waiting patient into active consultation.
    - Serializes via doctor/date advisory lock.
    - Acquires pessimistic row lock with_for_update().
    - Validates no other patient is currently in consultation for this doctor on this clinic date.
    - Transitions queue status to 'in_consultation' and appointment to 'in_progress'.
    - Backed by partial unique index 'uq_active_doctor_in_consultation'.
    """
    # 1. Fetch entry with row lock
    entry_query = (
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(
            selectinload(QueueEntry.patient),
            selectinload(QueueEntry.appointment),
        )
        .with_for_update()
    )
    res = await db.execute(entry_query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    # 2. Authorization Check
    await _verify_doctor_access(entry.doctor_id, current_user, db)

    # 3. Status Check
    if entry.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot call patient with status '{entry.status}'. Must be 'waiting'.",
        )

    # 4. Advisory lock to serialize simultaneous call-next requests for the same doctor/date
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:doc_id), hashtext(:c_date));"),
        {"doc_id": str(entry.doctor_id), "c_date": str(entry.queue_date)},
    )

    # 5. Check if another patient is already in consultation for this doctor on this clinic date
    active_consult_res = await db.execute(
        select(QueueEntry).where(
            QueueEntry.doctor_id == entry.doctor_id,
            QueueEntry.queue_date == entry.queue_date,
            QueueEntry.status == "in_consultation",
            QueueEntry.id != entry.id,
        )
    )
    if active_consult_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another patient is currently in consultation. Please complete or skip the active consultation first.",
        )

    # 6. Apply state transitions atomically
    now = datetime.now(timezone.utc)
    entry.status = "in_consultation"
    entry.called_at = now
    entry.position = 0
    entry.estimated_wait_minutes = 0
    if data and data.notes:
        entry.notes = data.notes

    if entry.appointment:
        entry.appointment.status = "in_progress"

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(f"Active consultation conflict caught: {exc}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another patient is currently in consultation with this doctor.",
        )

    # 7. Broadcast real-time update
    await queue_ws_manager.broadcast_to_doctor(
        str(entry.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(entry.doctor_id),
            "action": "PATIENT_CALLED",
            "token_display": entry.token_display,
            "token_number": entry.token_number,
            "timestamp": now.isoformat(),
        },
    )

    pat_name = entry.patient.full_name if entry.patient else "Patient"
    pat_email = entry.patient.email if entry.patient else None
    pat_phone = entry.patient.phone if entry.patient else None
    appt_tok = entry.appointment.appointment_token if entry.appointment else ""
    appt_time = str(entry.appointment.appointment_time) if entry.appointment else ""

    return DoctorQueueItemResponse(
        id=entry.id,
        token_number=entry.token_number,
        token_display=entry.token_display,
        position=0,
        status=entry.status,
        patient_id=entry.patient_id,
        patient_name=pat_name,
        patient_email=pat_email,
        patient_phone=pat_phone,
        appointment_id=entry.appointment_id,
        appointment_token=appt_tok,
        appointment_time=appt_time,
        checked_in_at=entry.checked_in_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
        notes=entry.notes,
    )


@router.post(
    "/{entry_id}/complete",
    response_model=DoctorQueueItemResponse,
    summary="Mark active consultation as completed",
)
async def complete_consultation(
    entry_id: uuid.UUID,
    data: Optional[QueueActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Marks an in-consultation queue entry as completed.
    Synchronizes appointment status to 'completed'.
    """
    entry_query = (
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(
            selectinload(QueueEntry.patient),
            selectinload(QueueEntry.appointment),
        )
        .with_for_update()
    )
    res = await db.execute(entry_query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    await _verify_doctor_access(entry.doctor_id, current_user, db)

    if entry.status != "in_consultation":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete consultation for entry with status '{entry.status}'. Must be 'in_consultation'.",
        )

    now = datetime.now(timezone.utc)
    entry.status = "completed"
    entry.completed_at = now
    if data and data.notes:
        entry.notes = data.notes

    if entry.appointment:
        entry.appointment.status = "completed"

    await db.commit()

    await queue_ws_manager.broadcast_to_doctor(
        str(entry.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(entry.doctor_id),
            "action": "COMPLETED",
            "token_display": entry.token_display,
            "token_number": entry.token_number,
            "timestamp": now.isoformat(),
        },
    )

    pat_name = entry.patient.full_name if entry.patient else "Patient"
    pat_email = entry.patient.email if entry.patient else None
    pat_phone = entry.patient.phone if entry.patient else None
    appt_tok = entry.appointment.appointment_token if entry.appointment else ""
    appt_time = str(entry.appointment.appointment_time) if entry.appointment else ""

    return DoctorQueueItemResponse(
        id=entry.id,
        token_number=entry.token_number,
        token_display=entry.token_display,
        position=0,
        status=entry.status,
        patient_id=entry.patient_id,
        patient_name=pat_name,
        patient_email=pat_email,
        patient_phone=pat_phone,
        appointment_id=entry.appointment_id,
        appointment_token=appt_tok,
        appointment_time=appt_time,
        checked_in_at=entry.checked_in_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
        notes=entry.notes,
    )


@router.post(
    "/{entry_id}/skip",
    response_model=DoctorQueueItemResponse,
    summary="Skip patient in queue",
)
async def skip_patient(
    entry_id: uuid.UUID,
    data: Optional[QueueActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Skips a waiting or in-consultation patient.
    Updates appointment status to 'no_show'.
    """
    entry_query = (
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(
            selectinload(QueueEntry.patient),
            selectinload(QueueEntry.appointment),
        )
        .with_for_update()
    )
    res = await db.execute(entry_query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    await _verify_doctor_access(entry.doctor_id, current_user, db)

    if entry.status not in ("waiting", "in_consultation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot skip entry with status '{entry.status}'. Must be 'waiting' or 'in_consultation'.",
        )

    now = datetime.now(timezone.utc)
    entry.status = "skipped"
    entry.position = 0
    if data and data.notes:
        entry.notes = data.notes

    if entry.appointment:
        entry.appointment.status = "no_show"

    await db.commit()

    await queue_ws_manager.broadcast_to_doctor(
        str(entry.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(entry.doctor_id),
            "action": "SKIPPED",
            "token_display": entry.token_display,
            "token_number": entry.token_number,
            "timestamp": now.isoformat(),
        },
    )

    pat_name = entry.patient.full_name if entry.patient else "Patient"
    pat_email = entry.patient.email if entry.patient else None
    pat_phone = entry.patient.phone if entry.patient else None
    appt_tok = entry.appointment.appointment_token if entry.appointment else ""
    appt_time = str(entry.appointment.appointment_time) if entry.appointment else ""

    return DoctorQueueItemResponse(
        id=entry.id,
        token_number=entry.token_number,
        token_display=entry.token_display,
        position=0,
        status=entry.status,
        patient_id=entry.patient_id,
        patient_name=pat_name,
        patient_email=pat_email,
        patient_phone=pat_phone,
        appointment_id=entry.appointment_id,
        appointment_token=appt_tok,
        appointment_time=appt_time,
        checked_in_at=entry.checked_in_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
        notes=entry.notes,
    )


@router.post(
    "/{entry_id}/recall",
    response_model=DoctorQueueItemResponse,
    summary="Recall a skipped patient back into active waiting queue",
)
async def recall_patient(
    entry_id: uuid.UUID,
    data: Optional[QueueActionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Recalls a skipped queue entry back into the waiting state.
    Restores appointment status to 'scheduled'.
    Fails if the appointment was cancelled.
    """
    entry_query = (
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(
            selectinload(QueueEntry.patient),
            selectinload(QueueEntry.appointment),
        )
        .with_for_update()
    )
    res = await db.execute(entry_query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    await _verify_doctor_access(entry.doctor_id, current_user, db)

    if entry.status != "skipped":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot recall entry with status '{entry.status}'. Only 'skipped' entries can be recalled.",
        )

    if entry.appointment and entry.appointment.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot recall a queue entry whose appointment has been cancelled",
        )

    now = datetime.now(timezone.utc)
    entry.status = "waiting"
    if data and data.notes:
        entry.notes = data.notes

    if entry.appointment:
        entry.appointment.status = "checked_in"

    await db.commit()

    await queue_ws_manager.broadcast_to_doctor(
        str(entry.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(entry.doctor_id),
            "action": "RECALLED",
            "token_display": entry.token_display,
            "token_number": entry.token_number,
            "timestamp": now.isoformat(),
        },
    )

    pat_name = entry.patient.full_name if entry.patient else "Patient"
    pat_email = entry.patient.email if entry.patient else None
    pat_phone = entry.patient.phone if entry.patient else None
    appt_tok = entry.appointment.appointment_token if entry.appointment else ""
    appt_time = str(entry.appointment.appointment_time) if entry.appointment else ""

    return DoctorQueueItemResponse(
        id=entry.id,
        token_number=entry.token_number,
        token_display=entry.token_display,
        position=entry.position,
        status=entry.status,
        patient_id=entry.patient_id,
        patient_name=pat_name,
        patient_email=pat_email,
        patient_phone=pat_phone,
        appointment_id=entry.appointment_id,
        appointment_token=appt_tok,
        appointment_time=appt_time,
        checked_in_at=entry.checked_in_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
        notes=entry.notes,
    )


@router.delete(
    "/{entry_id}",
    summary="Cancel queue entry and appointment",
)
async def cancel_queue_entry(
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancels a queue entry.
    - Patients can cancel their own entry only if it is waiting or skipped (cannot cancel in-consultation or completed).
    - Doctors/admins can cancel entries in their assigned queues.
    - Synchronizes appointment status to 'cancelled'.
    """
    entry_query = (
        select(QueueEntry)
        .where(QueueEntry.id == entry_id)
        .options(selectinload(QueueEntry.appointment))
        .with_for_update()
    )
    res = await db.execute(entry_query)
    entry = res.scalar_one_or_none()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue entry not found",
        )

    # Authorization Check
    is_owner = entry.patient_id == current_user.id
    if current_user.role == "patient" and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You can only cancel your own queue entry",
        )

    if entry.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Queue entry is already cancelled",
        )

    if entry.status in ("in_consultation", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a consultation that is already in progress or completed",
        )

    if current_user.role != "patient":
        # Doctor / Admin check
        await _verify_doctor_access(entry.doctor_id, current_user, db)

    now = datetime.now(timezone.utc)
    entry.status = "cancelled"
    entry.position = 0

    if entry.appointment:
        entry.appointment.status = "cancelled"
        entry.appointment.cancellation_reason = "Cancelled in queue"

    await db.commit()

    await queue_ws_manager.broadcast_to_doctor(
        str(entry.doctor_id),
        {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(entry.doctor_id),
            "action": "CANCELLED",
            "token_display": entry.token_display,
            "token_number": entry.token_number,
            "timestamp": now.isoformat(),
        },
    )

    return {"message": "Queue entry cancelled successfully", "id": str(entry_id)}


@router.websocket("/ws/{doctor_id}")
async def queue_websocket_endpoint(
    websocket: WebSocket,
    doctor_id: uuid.UUID,
):
    """
    Live real-time WebSocket channel scoped to a specific doctor's queue.
    Requires authentication via HttpOnly cookie or Authorization header during handshake.
    Rejects unauthorized or cross-origin connections with 1008 Policy Violation.
    """
    user = await authenticate_websocket(websocket)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify doctor room authorization before accepting socket connection
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        doc_res = await session.execute(
            select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.user))
        )
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if user.role == "doctor":
            if doctor.user_id != user.id:
                logger.warning(f"WS rejected: Doctor {user.id} attempted to subscribe to Doctor {doctor_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        elif user.role == "hospital_admin":
            admin_hosp = getattr(user, "hospital_id", None)
            if not admin_hosp or doctor.hospital_id != admin_hosp:
                logger.warning(f"WS rejected: Hospital admin {user.id} unauthorized for Doctor {doctor_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        elif user.role == "patient":
            clinic_today = _get_clinic_today()
            appt_res = await session.execute(
                select(Appointment.id).where(
                    Appointment.patient_id == user.id,
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == clinic_today,
                    Appointment.status != "cancelled",
                ).limit(1)
            )
            if appt_res.scalar_one_or_none() is None:
                logger.warning(f"WS rejected: Patient {user.id} has no active appointment with Doctor {doctor_id} today")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        elif user.role != "system_admin":
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    doc_room = str(doctor_id)
    await queue_ws_manager.connect(doc_room, websocket)

    try:
        while True:
            # Keepalive listener: clients can send ping or receive broadcasts
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        queue_ws_manager.disconnect(doc_room, websocket)
    except Exception as exc:
        logger.debug(f"WebSocket client error in room {doc_room}: {exc}")
        queue_ws_manager.disconnect(doc_room, websocket)
