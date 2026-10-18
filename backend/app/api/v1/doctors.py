import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.models.appointment import Appointment
from app.schemas.doctor import (
    DoctorListResponse,
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
    if slot_date < date.today():
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
    slots = []
    for slot_time in STANDARD_SLOTS:
        available = is_working_day and (slot_time not in booked_times)
        # If checking today, also ensure time hasn't passed
        if slot_date == date.today():
            now_time = datetime.now().strftime("%H:%M")
            if slot_time <= now_time:
                available = False

        slots.append(DoctorSlot(time=slot_time, is_available=available))

    return DoctorSlotsDayResponse(
        doctor_id=doctor_id,
        date=slot_date,
        day_of_week=day_of_week,
        is_working_day=is_working_day,
        slots=slots,
    )
