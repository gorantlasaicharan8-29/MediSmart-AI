import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
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
from app.models.queue import QueueEntry
from app.models.user import User
from app.schemas.ml import WaitingTimePredictionRequest
from app.schemas.queue_prediction import (
    DoctorQueueAnalyticsResponse,
    DoctorQueueItemPrediction,
    PatientQueuePredictionResponse,
)
from app.services.ml_prediction import ml_prediction_service

logger = logging.getLogger("medismart.services.queue_waiting_time")

# Clinical baseline durations per specialty (used as fallback when historical data < 3 samples)
SPECIALTY_BASELINES: Dict[str, float] = {
    "Cardiology": 18.0,
    "Neurology": 20.0,
    "Oncology": 22.0,
    "Orthopedics": 16.0,
    "Gastroenterology": 15.0,
    "Nephrology": 16.0,
    "Pulmonology": 15.0,
    "Dermatology": 12.0,
    "Pediatrics": 14.0,
    "General Medicine": 12.0,
}
DEFAULT_CONSULTATION_BASELINE = 15.0


class QueueWaitingTimeService:
    """
    Intelligent real-time queue waiting-time estimation engine.
    Combines:
    - Live queue state (waiting patients, positions)
    - Active consultation remaining time decay
    - Doctor's empirical historical consultation durations
    - Serialized XGBoost machine learning prediction pipeline
    - Fallback protection
    """

    @classmethod
    async def get_doctor_historical_avg_minutes(
        cls,
        doctor_id: uuid.UUID,
        specialty: Optional[str],
        db: AsyncSession,
    ) -> float:
        """
        Calculates doctor's empirical average consultation duration from completed queue records.
        Falls back to specialty standard baseline if fewer than 3 completed consultations exist.
        """
        stmt = (
            select(
                func.count(QueueEntry.id),
                func.avg(func.extract("epoch", QueueEntry.completed_at - QueueEntry.called_at) / 60.0),
            )
            .where(
                QueueEntry.doctor_id == doctor_id,
                QueueEntry.status == "completed",
                QueueEntry.completed_at.isnot(None),
                QueueEntry.called_at.isnot(None),
                QueueEntry.completed_at > QueueEntry.called_at,
            )
        )
        res = await db.execute(stmt)
        count, avg_duration = res.one_or_none() or (0, None)

        if count and count >= 3 and avg_duration and 3.0 <= float(avg_duration) <= 90.0:
            return round(float(avg_duration), 1)

        # Baseline fallback
        if specialty and specialty in SPECIALTY_BASELINES:
            return SPECIALTY_BASELINES[specialty]

        return DEFAULT_CONSULTATION_BASELINE

    @classmethod
    async def get_active_consultation_info(
        cls,
        doctor_id: uuid.UUID,
        clinic_date: date,
        db: AsyncSession,
    ) -> Tuple[bool, Optional[str], Optional[float], Optional[datetime]]:
        """
        Inspects if doctor currently has a patient in consultation, and computes elapsed minutes.
        Returns (is_active, token_display, elapsed_minutes, called_at).
        """
        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.doctor_id == doctor_id,
                QueueEntry.queue_date == clinic_date,
                QueueEntry.status == "in_consultation",
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        active_entry = res.scalar_one_or_none()

        if not active_entry or not active_entry.called_at:
            return False, None, None, None

        now_utc = datetime.now(timezone.utc)
        called_at = active_entry.called_at
        if called_at.tzinfo is None:
            called_at = called_at.replace(tzinfo=timezone.utc)

        elapsed = max(0.0, (now_utc - called_at).total_seconds() / 60.0)
        return True, active_entry.token_display, round(elapsed, 1), called_at

    @classmethod
    def calculate_prediction_for_entry(
        cls,
        entry: QueueEntry,
        doctor: Doctor,
        hospital: Optional[Hospital],
        patients_ahead: int,
        is_active_consultation: bool,
        active_elapsed_minutes: Optional[float],
        historical_avg_minutes: float,
        clinic_today: date,
    ) -> Tuple[float, int, bool, str]:
        """
        Computes the waiting time for a single queue entry using XGBoost model with
        active-consultation decay calibration.
        Returns (raw_wait_minutes, rounded_wait_minutes, is_fallback, model_name).
        """
        # If already inside consultation room, wait time is 0
        if entry.status == "in_consultation":
            return 0.0, 0, False, "active_consultation"

        # Calculate remaining duration of active consultation
        if is_active_consultation and active_elapsed_minutes is not None:
            active_remaining = max(1.0, historical_avg_minutes - active_elapsed_minutes)
        else:
            active_remaining = 0.0

        # If next in line and no active consultation, doctor is ready immediately
        if patients_ahead == 0 and not is_active_consultation:
            return 0.0, 0, False, "next_in_line"

        # If next in line and doctor is consulting, wait time is the remaining active time
        if patients_ahead == 0 and is_active_consultation:
            wait = active_remaining
            return round(wait, 1), int(round(wait)), False, "active_consultation_remaining"

        # Extract slot hour and minute
        slot_hour = 10
        slot_minute = 0
        arrival_lead = 0.0

        if entry.appointment and entry.appointment.appointment_time:
            appt_time = entry.appointment.appointment_time
            slot_hour = appt_time.hour
            slot_minute = appt_time.minute

            if entry.checked_in_at:
                checked_in = entry.checked_in_at
                if checked_in.tzinfo:
                    checked_in_local = checked_in.astimezone(CLINIC_TZ)
                else:
                    checked_in_local = checked_in

                appt_dt = datetime.combine(entry.queue_date, appt_time)
                diff = (appt_dt - checked_in_local.replace(tzinfo=None)).total_seconds() / 60.0
                arrival_lead = max(-180.0, min(180.0, diff))

        day_of_week = clinic_today.weekday()

        # Build feature request for existing XGBoost pipeline
        feature_req = WaitingTimePredictionRequest(
            doctor_specialty=doctor.specialty or "General Medicine",
            doctor_experience_years=doctor.experience_years or 5,
            day_of_week=day_of_week,
            slot_hour=slot_hour,
            slot_minute=slot_minute,
            arrival_lead_minutes=round(arrival_lead, 1),
            queue_position_at_checkin=entry.token_number or entry.position or 1,
            patients_waiting_ahead=patients_ahead,
            is_doctor_active_consultation=1 if is_active_consultation else 0,
            historical_avg_consultation_minutes=historical_avg_minutes,
        )

        try:
            ml_res = ml_prediction_service.predict_waiting_time(feature_req)
            raw_wait = ml_res.predicted_wait_minutes
            model_name = ml_res.model_name
            is_fallback = False

            # Calibrate ML prediction with active consultation remaining time
            if is_active_consultation and active_elapsed_minutes is not None:
                # Minimum bound: cannot be less than active patient remaining plus queue ahead
                min_wait = active_remaining + (patients_ahead * (historical_avg_minutes * 0.6))
                raw_wait = max(raw_wait, min_wait)

                # If active consultation has overrun expected duration, add gentle delay penalty
                if active_elapsed_minutes > historical_avg_minutes:
                    overrun = active_elapsed_minutes - historical_avg_minutes
                    raw_wait += round(overrun * 0.4, 1)

        except Exception as err:
            logger.warning("ML prediction failed; falling back to historical queue rate: %s", err)
            raw_wait = active_remaining + (patients_ahead * historical_avg_minutes)
            model_name = "historical_average_fallback"
            is_fallback = True

        rounded_wait = int(round(raw_wait))
        return round(raw_wait, 1), rounded_wait, is_fallback, model_name

    @classmethod
    async def predict_for_patient_queue(
        cls,
        patient_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[PatientQueuePredictionResponse]:
        """
        Retrieves active queue entry for patient today and computes intelligent real-time prediction.
        """
        clinic_today = datetime.now(CLINIC_TZ).date()

        stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.patient_id == patient_id,
                QueueEntry.queue_date == clinic_today,
                QueueEntry.status.in_(["waiting", "in_consultation"]),
            )
            .options(
                selectinload(QueueEntry.appointment),
                selectinload(QueueEntry.doctor).selectinload(Doctor.user),
                selectinload(QueueEntry.hospital),
            )
            .order_by(QueueEntry.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        entry = res.scalar_one_or_none()

        if not entry:
            return None

        doctor = entry.doctor
        hospital = entry.hospital

        # 1. Count patients ahead in waiting status
        ahead_stmt = select(func.count(QueueEntry.id)).where(
            QueueEntry.doctor_id == entry.doctor_id,
            QueueEntry.queue_date == clinic_today,
            QueueEntry.status == "waiting",
            QueueEntry.token_number < entry.token_number,
        )
        ahead_res = await db.execute(ahead_stmt)
        patients_ahead = ahead_res.scalar() or 0

        # 2. Check active consultation
        is_active, _, active_elapsed, _ = await cls.get_active_consultation_info(
            entry.doctor_id, clinic_today, db
        )

        # 3. Doctor historical average
        hist_avg = await cls.get_doctor_historical_avg_minutes(
            entry.doctor_id, doctor.specialty if doctor else None, db
        )

        # 4. Compute prediction
        raw_wait, rounded_wait, is_fallback, model_name = cls.calculate_prediction_for_entry(
            entry=entry,
            doctor=doctor,
            hospital=hospital,
            patients_ahead=patients_ahead,
            is_active_consultation=is_active,
            active_elapsed_minutes=active_elapsed,
            historical_avg_minutes=hist_avg,
            clinic_today=clinic_today,
        )

        doc_user_name = doctor.user.full_name if (doctor and doctor.user) else "Medical Specialist"
        hosp_name = hospital.name if hospital else "Affiliated Hospital"

        if entry.status == "in_consultation":
            display_wait = "In Consultation"
        elif rounded_wait <= 1:
            display_wait = "< 2 mins"
        else:
            display_wait = f"{rounded_wait} mins"

        now_dt = datetime.now(timezone.utc)

        return PatientQueuePredictionResponse(
            queue_entry_id=entry.id,
            token_number=entry.token_number,
            token_display=entry.token_display,
            position=patients_ahead + 1 if entry.status == "waiting" else 0,
            patients_ahead=patients_ahead,
            estimated_wait_minutes=rounded_wait,
            predicted_wait_minutes_raw=raw_wait,
            display_wait_time=display_wait,
            queue_status=entry.status,
            doctor_id=entry.doctor_id,
            doctor_name=doc_user_name,
            doctor_specialty=doctor.specialty if doctor else "General Medicine",
            hospital_name=hosp_name,
            is_doctor_active_consultation=is_active,
            current_consultation_elapsed_minutes=active_elapsed,
            historical_avg_consultation_minutes=hist_avg,
            model_name=model_name,
            model_version="1.0.0",
            is_fallback=is_fallback,
            prediction_timestamp=now_dt,
            explanation=(
                "Your estimated waiting time is based on current queue activity and historical consultation durations."
            ),
        )

    @classmethod
    async def get_doctor_queue_analytics(
        cls,
        doctor_id: uuid.UUID,
        db: AsyncSession,
    ) -> DoctorQueueAnalyticsResponse:
        """
        Calculates comprehensive intelligent queue analytics for Doctor Dashboard.
        """
        clinic_today = datetime.now(CLINIC_TZ).date()

        # Doctor profile
        doc_stmt = (
            select(Doctor)
            .where(Doctor.id == doctor_id)
            .options(selectinload(Doctor.user), selectinload(Doctor.hospital))
        )
        doc_res = await db.execute(doc_stmt)
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor profile not found")

        doc_name = doctor.user.full_name if doctor.user else "Doctor"
        specialty = doctor.specialty or "General Medicine"

        # Active consultation
        is_active, active_tok, active_elapsed, _ = await cls.get_active_consultation_info(
            doctor_id, clinic_today, db
        )

        # Historical average
        hist_avg = await cls.get_doctor_historical_avg_minutes(doctor_id, specialty, db)

        # Completed today
        comp_stmt = select(func.count(QueueEntry.id)).where(
            QueueEntry.doctor_id == doctor_id,
            QueueEntry.queue_date == clinic_today,
            QueueEntry.status == "completed",
        )
        comp_res = await db.execute(comp_stmt)
        total_completed = comp_res.scalar() or 0

        # Waiting entries today
        waiting_stmt = (
            select(QueueEntry)
            .where(
                QueueEntry.doctor_id == doctor_id,
                QueueEntry.queue_date == clinic_today,
                QueueEntry.status == "waiting",
            )
            .options(
                selectinload(QueueEntry.appointment),
                selectinload(QueueEntry.patient),
            )
            .order_by(QueueEntry.token_number.asc())
        )
        waiting_res = await db.execute(waiting_stmt)
        waiting_entries = waiting_res.scalars().all()

        waiting_count = len(waiting_entries)

        # Generate individual waiting item predictions
        waiting_predictions: List[DoctorQueueItemPrediction] = []
        total_wait_minutes = 0

        for idx, w_entry in enumerate(waiting_entries):
            patients_ahead = idx
            raw_wait, rounded_wait, _, _ = cls.calculate_prediction_for_entry(
                entry=w_entry,
                doctor=doctor,
                hospital=doctor.hospital,
                patients_ahead=patients_ahead,
                is_active_consultation=is_active,
                active_elapsed_minutes=active_elapsed,
                historical_avg_minutes=hist_avg,
                clinic_today=clinic_today,
            )
            total_wait_minutes = max(total_wait_minutes, rounded_wait)

            pat_name = w_entry.patient.full_name if w_entry.patient else "Patient"
            appt_time_str = (
                str(w_entry.appointment.appointment_time)
                if (w_entry.appointment and w_entry.appointment.appointment_time)
                else None
            )

            waiting_predictions.append(
                DoctorQueueItemPrediction(
                    queue_entry_id=w_entry.id,
                    token_display=w_entry.token_display,
                    token_number=w_entry.token_number,
                    position=idx + 1,
                    patient_name=pat_name,
                    appointment_time=appt_time_str,
                    predicted_wait_minutes=rounded_wait,
                    status=w_entry.status,
                )
            )

        # Congestion classification
        if waiting_count == 0:
            congestion_status = "low"
            analytics_summary = "Queue is clear. No waiting patients."
        elif waiting_count <= 2 or total_wait_minutes <= 30:
            congestion_status = "low"
            analytics_summary = f"Patient flow is optimal with {waiting_count} patient(s) waiting."
        elif waiting_count <= 5 or total_wait_minutes <= 60:
            congestion_status = "moderate"
            analytics_summary = f"Moderate queue pace. Est. clearing time is {total_wait_minutes} mins."
        elif waiting_count <= 8 or total_wait_minutes <= 120:
            congestion_status = "high"
            analytics_summary = f"High patient volume. Consider pacing next calls."
        else:
            congestion_status = "congested"
            analytics_summary = f"Clinic queue is congested ({waiting_count} waiting). Immediate attention recommended."

        return DoctorQueueAnalyticsResponse(
            doctor_id=doctor_id,
            doctor_name=doc_name,
            specialty=specialty,
            queue_date=clinic_today,
            waiting_patients_count=waiting_count,
            currently_consulting_token=active_tok,
            current_consultation_elapsed_minutes=active_elapsed,
            average_consultation_duration_minutes=hist_avg,
            total_completed_today=total_completed,
            queue_congestion_status=congestion_status,
            estimated_clearing_time_minutes=total_wait_minutes,
            waiting_queue=waiting_predictions,
            model_name="xgboost",
            model_version="1.0.0",
            prediction_timestamp=datetime.now(timezone.utc),
            analytics_summary=analytics_summary,
        )

