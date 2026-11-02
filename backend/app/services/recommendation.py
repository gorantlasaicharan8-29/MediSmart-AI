import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

try:
    from zoneinfo import ZoneInfo
    CLINIC_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.doctor import DoctorResponse
from app.schemas.recommendation import (
    DoctorRecommendationItem,
    DoctorRecommendationRequest,
    DoctorRecommendationResponse,
)

logger = logging.getLogger(__name__)

# Standard 30-minute consultation clinic slots
STANDARD_SLOTS = [
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30",
    "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30"
]


class DoctorRecommendationService:
    """
    Transparent, explainable recommendation engine for doctors.
    Computes weighted match scores (0-100) based on actual application data:
    - Specialization (35%)
    - Location / City (20%)
    - Hospital Affiliation (15%)
    - Consultation Fee Budget (15%)
    - Confirmed Slot Availability on Requested Date (15%)
    """

    @classmethod
    async def get_recommendations(
        cls,
        preferences: DoctorRecommendationRequest,
        db: AsyncSession,
    ) -> DoctorRecommendationResponse:
        clinic_now = datetime.now(CLINIC_TZ)
        clinic_today = clinic_now.date()

        # 1. Date Validation
        target_date = preferences.preferred_date or clinic_today
        if target_date < clinic_today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot request recommendations for past dates.",
            )

        # 2. Query Active Doctors with User and Hospital details
        stmt = (
            select(Doctor)
            .join(Doctor.user)
            .join(Doctor.hospital)
            .where(
                User.is_active == True,
                Hospital.is_active == True,
            )
            .options(
                selectinload(Doctor.user),
                selectinload(Doctor.hospital),
            )
        )
        result = await db.execute(stmt)
        all_doctors = result.scalars().all()

        total_evaluated = len(all_doctors)
        if total_evaluated == 0:
            return DoctorRecommendationResponse(
                items=[],
                total_evaluated=0,
                preferred_date=target_date,
                preferences_applied=preferences,
            )

        # 3. Batch fetch booked appointments for target_date to avoid N+1 queries
        booked_stmt = select(
            Appointment.doctor_id,
            Appointment.appointment_time,
        ).where(
            Appointment.appointment_date == target_date,
            Appointment.status != "cancelled",
        )
        booked_result = await db.execute(booked_stmt)
        booked_slots_by_doctor: Dict[uuid.UUID, Set[str]] = defaultdict(set)
        for doc_id, appt_time in booked_result.all():
            if appt_time:
                booked_slots_by_doctor[doc_id].add(appt_time.strftime("%H:%M"))

        day_of_week = target_date.strftime("%A")
        now_time_str = clinic_now.strftime("%H:%M") if target_date == clinic_today else None

        scored_items: List[DoctorRecommendationItem] = []

        # 4. Evaluate each doctor transparently
        for doctor in all_doctors:
            explanations: List[str] = []
            breakdown: Dict[str, float] = {}
            score = 0.0

            # --- A. SPECIALIZATION MATCH (Max 35 points) ---
            if preferences.specialty and preferences.specialty.strip():
                req_spec = preferences.specialty.strip().lower()
                doc_spec = (doctor.specialty or "").strip().lower()

                if doc_spec == req_spec:
                    score_spec = 35.0
                    explanations.append(f"Specializes in {doctor.specialty} matching your preference.")
                elif req_spec in doc_spec or doc_spec in req_spec:
                    score_spec = 28.0
                    explanations.append(f"Specializes in {doctor.specialty} closely related to your request.")
                else:
                    # Clinically strict: if patient explicitly searched for a specific specialty,
                    # doctors from irrelevant specialties should not be recommended.
                    continue
            else:
                score_spec = 20.0  # Neutral baseline when no specialty requested
                if doctor.specialty:
                    explanations.append(f"Specializes in {doctor.specialty}.")

            score += score_spec
            breakdown["specialty"] = score_spec

            # --- B. LOCATION / CITY MATCH (Max 20 points) ---
            hosp_city = (doctor.hospital.city or "").strip().lower() if doctor.hospital else ""
            hosp_state = (doctor.hospital.state or "").strip().lower() if doctor.hospital else ""
            hosp_address = (doctor.hospital.address or "").strip().lower() if doctor.hospital else ""

            if preferences.city and preferences.city.strip():
                req_city = preferences.city.strip().lower()
                if hosp_city == req_city:
                    score_loc = 20.0
                    explanations.append(f"Located in your preferred city: {doctor.hospital.city}.")
                elif req_city in hosp_city or req_city in hosp_state or req_city in hosp_address:
                    score_loc = 15.0
                    explanations.append(f"Conveniently situated in {doctor.hospital.city}, {doctor.hospital.state}.")
                else:
                    score_loc = 0.0
            else:
                score_loc = 15.0  # Neutral baseline
                if doctor.hospital:
                    explanations.append(f"Practicing at {doctor.hospital.name}, {doctor.hospital.city}.")

            score += score_loc
            breakdown["location"] = score_loc

            # --- C. HOSPITAL PREFERENCE (Max 15 points) ---
            if preferences.hospital_id:
                if doctor.hospital_id == preferences.hospital_id:
                    score_hosp = 15.0
                    explanations.append(f"Affiliated directly with your selected hospital ({doctor.hospital.name}).")
                else:
                    score_hosp = 0.0
            elif preferences.hospital_name and preferences.hospital_name.strip():
                req_hosp = preferences.hospital_name.strip().lower()
                doc_hosp = (doctor.hospital.name or "").strip().lower() if doctor.hospital else ""
                if req_hosp in doc_hosp:
                    score_hosp = 15.0
                    explanations.append(f"Affiliated directly with {doctor.hospital.name}.")
                else:
                    score_hosp = 0.0
            else:
                score_hosp = 10.0  # Neutral baseline

            score += score_hosp
            breakdown["hospital"] = score_hosp

            # --- D. CONSULTATION FEE BUDGET MATCH (Max 15 points) ---
            if preferences.max_fee is not None:
                max_budget = float(preferences.max_fee)
                if doctor.consultation_fee is not None:
                    doc_fee = float(doctor.consultation_fee)
                    if doc_fee <= max_budget:
                        score_fee = 15.0
                        explanations.append(f"Consultation fee ₹{int(doc_fee)} is within your ₹{int(max_budget)} budget.")
                    elif doc_fee <= max_budget * 1.15:
                        score_fee = 8.0
                        explanations.append(f"Consultation fee ₹{int(doc_fee)} is close to your ₹{int(max_budget)} budget.")
                    elif doc_fee <= max_budget * 1.30:
                        score_fee = 4.0
                    else:
                        score_fee = 0.0
                else:
                    score_fee = 10.0
            else:
                score_fee = 12.0  # Neutral baseline
                if doctor.consultation_fee is not None:
                    explanations.append(f"Consultation fee: ₹{int(doctor.consultation_fee)}.")

            score += score_fee
            breakdown["fee"] = score_fee

            # --- E. CONFIRMED APPOINTMENT AVAILABILITY (Max 15 points) ---
            is_slot_available = False
            earliest_slot: Optional[str] = None

            if not doctor.is_available:
                score_avail = 0.0
                explanations.append("Doctor is currently marked as unavailable for appointments.")
            else:
                avail_days = doctor.available_days or []
                is_working_day = day_of_week in avail_days

                if not is_working_day:
                    score_avail = 3.0
                    working_summary = ", ".join(avail_days[:3])
                    explanations.append(f"Consults on {working_summary} (off-duty on {day_of_week}).")
                else:
                    doc_booked = booked_slots_by_doctor.get(doctor.id, set())
                    open_slots = []
                    for s in STANDARD_SLOTS:
                        if s in doc_booked:
                            continue
                        if now_time_str and s <= now_time_str:
                            continue
                        open_slots.append(s)

                    if open_slots:
                        score_avail = 15.0
                        is_slot_available = True
                        earliest_slot = open_slots[0]
                        explanations.append(
                            f"Confirmed open slot at {earliest_slot} on {target_date.strftime('%d %b %Y')} ({len(open_slots)} open)."
                        )
                    else:
                        score_avail = 5.0
                        explanations.append(f"Working on {day_of_week}, but all consultation slots are currently booked.")

            score += score_avail
            breakdown["availability"] = score_avail

            # --- F. CLINICAL CREDENTIALS & EXPERIENCE EXPLANATIONS ---
            if doctor.experience_years and doctor.experience_years >= 5:
                qual_str = f" ({doctor.qualification})" if doctor.qualification else ""
                explanations.append(f"{doctor.experience_years}+ years clinical experience{qual_str}.")
            elif doctor.qualification:
                explanations.append(f"Qualified: {doctor.qualification}.")

            if doctor.credential_status == "verified" and doctor.hospital:
                explanations.append(f"Verified Practitioner with {doctor.hospital.name}.")

            final_score = int(min(100, max(0, round(score))))

            # Build DoctorResponse schema object
            doc_response = DoctorResponse.model_validate(doctor)

            scored_items.append(
                DoctorRecommendationItem(
                    doctor=doc_response,
                    match_score=final_score,
                    match_percentage=final_score,
                    explanations=explanations,
                    next_available_slot=earliest_slot,
                    next_available_date=target_date,
                    is_slot_available=is_slot_available,
                    score_breakdown=breakdown,
                )
            )

        # 5. Sort Recommendations:
        # Highest match score first, then available slot flag, then experience descending, then fee ascending
        scored_items.sort(
            key=lambda x: (
                x.match_score,
                1 if x.is_slot_available else 0,
                x.doctor.experience_years or 0,
                -(x.doctor.consultation_fee or 999999.0),
            ),
            reverse=True,
        )

        # 6. Apply limit
        top_items = scored_items[: preferences.limit]

        return DoctorRecommendationResponse(
            items=top_items,
            total_evaluated=total_evaluated,
            preferred_date=target_date,
            preferences_applied=preferences,
        )

