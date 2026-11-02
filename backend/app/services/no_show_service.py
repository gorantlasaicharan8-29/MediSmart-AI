"""
Intelligent Appointment No-Show Prediction & Analytics Service for MediSmart.

Combines the trained Logistic Regression pipeline with actual appointment telemetry:
- Extracts lead times, scheduling timing, prior patient attendance history, and specialty.
- Predicts calibrated no-show probabilities and assigns transparent risk bands (Low, Medium, High).
- Generates explainable risk factor rationales and clinical follow-up recommendations.
- Computes aggregate hospital analytics (attendance rates, risk distributions, specialty trends).
- Dispatches idempotent smart reminders via NotificationService.
"""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.ml import NoShowPredictionRequest
from app.schemas.no_show import (
    AppointmentNoShowRiskResponse,
    DoctorAppointmentRiskItem,
    DoctorAppointmentsRiskListResponse,
    HospitalNoShowAnalyticsResponse,
    RiskDistributionSummary,
    RiskFactorExplanation,
    SendReminderResponse,
    SpecialtyNoShowTrend,
)
from app.services.ml_prediction import ml_prediction_service
from app.services.notification import notification_service

logger = logging.getLogger("medismart.services.no_show")

# Documented calibrated risk thresholds based on validation prevalence (~23.5%)
THRESHOLD_LOW_RISK = 0.25      # Below or near baseline population prevalence
THRESHOLD_MEDIUM_RISK = 0.45   # Elevated risk (~1.5x - 2x base rate)
# Probabilities >= 0.45 are classified as High Risk


class NoShowRiskService:
    """Centralized service for appointment attendance risk scoring and analytics."""

    @staticmethod
    def classify_risk(probability: float) -> Tuple[str, str]:
        """
        Maps probability to standardized risk level and display label.
        - < 0.25: Low Risk
        - 0.25 - 0.45: Medium Risk
        - >= 0.45: High Risk
        """
        if probability < THRESHOLD_LOW_RISK:
            return "low", "Low Risk"
        elif probability < THRESHOLD_MEDIUM_RISK:
            return "medium", "Medium Risk"
        else:
            return "high", "High Risk"

    @classmethod
    def generate_risk_factors(
        cls,
        lead_time_days: int,
        day_of_week: int,
        slot_hour: int,
        is_weekend: int,
        prior_appointments: int,
        prior_no_shows: int,
        has_notes: int,
        consultation_fee: float,
    ) -> List[RiskFactorExplanation]:
        """
        Extracts human-understandable, data-backed reasons for the risk score.
        Never fabricates factors not present in the record.
        """
        factors: List[RiskFactorExplanation] = []

        # 1. Booking Lead Time
        if lead_time_days > 7:
            factors.append(
                RiskFactorExplanation(
                    factor="Booking Lead Time",
                    impact="increases_risk",
                    description=f"Booked {lead_time_days} days in advance (longer lead time increases risk of scheduling conflicts).",
                )
            )
        elif lead_time_days <= 1:
            factors.append(
                RiskFactorExplanation(
                    factor="Booking Lead Time",
                    impact="decreases_risk",
                    description="Booked within 24 hours of appointment (short lead time indicates high attendance commitment).",
                )
            )

        # 2. Historical Patient Attendance
        if prior_no_shows > 0:
            factors.append(
                RiskFactorExplanation(
                    factor="Historical Attendance",
                    impact="increases_risk",
                    description=f"Patient has {prior_no_shows} recorded unexcused absence(s) in past visits.",
                )
            )
        elif prior_appointments >= 2:
            factors.append(
                RiskFactorExplanation(
                    factor="Historical Attendance",
                    impact="decreases_risk",
                    description=f"Reliable past attendance record ({prior_appointments} completed consultations with zero absences).",
                )
            )

        # 3. Schedule Timing
        if is_weekend == 1:
            factors.append(
                RiskFactorExplanation(
                    factor="Weekend Schedule",
                    impact="increases_risk",
                    description="Weekend consultation slots exhibit higher variance in attendance.",
                )
            )
        elif 9 <= slot_hour <= 11:
            factors.append(
                RiskFactorExplanation(
                    factor="Morning Consultation Slot",
                    impact="decreases_risk",
                    description="Morning clinic slots historically have the highest punctual check-in rates.",
                )
            )

        # 4. Clinical Notes
        if has_notes == 1:
            factors.append(
                RiskFactorExplanation(
                    factor="Pre-consultation Notes",
                    impact="decreases_risk",
                    description="Patient provided detailed clinical notes during booking.",
                )
            )

        return factors

    @classmethod
    def get_suggested_action(cls, risk_level: str) -> Tuple[str, bool]:
        """Returns action recommendation and reminder boolean."""
        if risk_level == "high":
            return (
                "Automated appointment reminder strongly recommended. Consider patient confirmation 24 hours prior.",
                True,
            )
        elif risk_level == "medium":
            return (
                "Automated appointment reminder recommended 48 hours prior to consultation.",
                True,
            )
        else:
            return (
                "Standard clinical workflow. Routine notification scheduled on consultation morning.",
                False,
            )

    @classmethod
    async def extract_appointment_features(
        cls,
        appointment: Appointment,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Derives all 10 ML input features for an appointment safely from the database.
        Includes query for historical attendance prior to the appointment date.
        """
        # 1. Lead time days
        created_dt = appointment.created_at
        if created_dt:
            created_date = created_dt.date() if isinstance(created_dt, datetime) else created_dt
            diff = (appointment.appointment_date - created_date).days
            lead_time_days = max(0, min(365, diff))
        else:
            lead_time_days = 0

        # 2. Timing
        appt_date = appointment.appointment_date
        day_of_week = appt_date.weekday()
        slot_hour = appointment.appointment_time.hour
        is_weekend = 1 if day_of_week in (5, 6) else 0

        # 3. Doctor specialty & fee
        specialty = appointment.doctor.specialty if appointment.doctor else "General Medicine"
        fee = float(appointment.doctor.consultation_fee) if appointment.doctor and appointment.doctor.consultation_fee else 500.0

        # 4. Has notes
        has_notes = 1 if appointment.notes and appointment.notes.strip() else 0

        # 5. Patient prior attendance strictly prior to this appointment date
        prior_q = select(
            func.count(Appointment.id).label("total_prior"),
            func.count(Appointment.id).filter(Appointment.status == "no_show").label("prior_no_shows"),
        ).where(
            and_(
                Appointment.patient_id == appointment.patient_id,
                Appointment.appointment_date < appointment.appointment_date,
                Appointment.status != "cancelled",
            )
        )
        prior_res = await db.execute(prior_q)
        prior_row = prior_res.one_or_none()
        prior_appointments = prior_row.total_prior if prior_row else 0
        prior_no_shows = prior_row.prior_no_shows if prior_row else 0
        prior_rate = (prior_no_shows / prior_appointments) if prior_appointments > 0 else 0.0

        return {
            "doctor_specialty": specialty,
            "lead_time_days": lead_time_days,
            "day_of_week": day_of_week,
            "slot_hour": slot_hour,
            "is_weekend": is_weekend,
            "consultation_fee": fee,
            "patient_prior_appointments": prior_appointments,
            "patient_prior_no_shows": prior_no_shows,
            "patient_prior_no_show_rate": round(prior_rate, 4),
            "has_notes": has_notes,
        }

    @classmethod
    async def predict_for_appointment(
        cls,
        appointment_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[AppointmentNoShowRiskResponse]:
        """
        Calculates comprehensive no-show risk assessment for a specific appointment.
        """
        query = (
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(
                selectinload(Appointment.doctor).selectinload(Doctor.user),
                selectinload(Appointment.hospital),
                selectinload(Appointment.patient),
            )
        )
        res = await db.execute(query)
        appointment = res.scalar_one_or_none()
        if not appointment:
            return None

        features = await cls.extract_appointment_features(appointment, db)

        # Call existing ML prediction service
        ml_request = NoShowPredictionRequest(**features)
        ml_res = ml_prediction_service.predict_no_show(ml_request)

        risk_level, risk_label = cls.classify_risk(ml_res.no_show_probability)
        suggested_action, reminder_recommended = cls.get_suggested_action(risk_level)
        risk_factors = cls.generate_risk_factors(
            lead_time_days=features["lead_time_days"],
            day_of_week=features["day_of_week"],
            slot_hour=features["slot_hour"],
            is_weekend=features["is_weekend"],
            prior_appointments=features["patient_prior_appointments"],
            prior_no_shows=features["patient_prior_no_shows"],
            has_notes=features["has_notes"],
            consultation_fee=features["consultation_fee"],
        )

        pat_name = appointment.patient.full_name if appointment.patient else "Patient"
        doc_name = (
            appointment.doctor.user.full_name
            if appointment.doctor and appointment.doctor.user
            else "Doctor"
        )
        doc_spec = appointment.doctor.specialty if appointment.doctor else "General Medicine"
        hosp_name = appointment.hospital.name if appointment.hospital else "MediSmart Clinic"

        return AppointmentNoShowRiskResponse(
            appointment_id=appointment.id,
            appointment_token=appointment.appointment_token,
            patient_id=appointment.patient_id,
            patient_name=pat_name,
            doctor_id=appointment.doctor_id,
            doctor_name=doc_name,
            doctor_specialty=doc_spec,
            hospital_name=hosp_name,
            appointment_date=appointment.appointment_date,
            appointment_time=appointment.appointment_time,
            status=appointment.status,
            no_show_probability=ml_res.no_show_probability,
            risk_level=risk_level,
            risk_display_label=risk_label,
            predicted_no_show=ml_res.predicted_no_show,
            decision_threshold=ml_res.decision_threshold,
            risk_factors=risk_factors,
            suggested_action=suggested_action,
            reminder_recommended=reminder_recommended,
            features_used=features,
            model_name=ml_res.model_name,
            model_version=ml_res.model_version,
            is_synthetic_model=True,
        )

    @classmethod
    async def get_doctor_appointments_risk_list(
        cls,
        doctor_id: uuid.UUID,
        db: AsyncSession,
        date_filter: Optional[date] = None,
        risk_level_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> DoctorAppointmentsRiskListResponse:
        """
        Retrieves doctor's appointments with risk scores, supporting risk filtering.
        """
        query = (
            select(Appointment)
            .where(
                and_(
                    Appointment.doctor_id == doctor_id,
                    Appointment.status.in_(["scheduled", "checked_in"]),
                )
            )
            .options(
                selectinload(Appointment.doctor).selectinload(Doctor.user),
                selectinload(Appointment.patient),
            )
            .order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
        )

        if date_filter:
            query = query.where(Appointment.appointment_date == date_filter)

        res = await db.execute(query)
        all_appts = res.scalars().all()

        scored_items: List[DoctorAppointmentRiskItem] = []
        high_cnt = 0
        med_cnt = 0
        low_cnt = 0
        total_prob = 0.0

        for appt in all_appts:
            feats = await cls.extract_appointment_features(appt, db)
            ml_req = NoShowPredictionRequest(**feats)
            ml_out = ml_prediction_service.predict_no_show(ml_req)

            prob = ml_out.no_show_probability
            total_prob += prob
            r_level, r_label = cls.classify_risk(prob)
            action, rem_rec = cls.get_suggested_action(r_level)

            if r_level == "high":
                high_cnt += 1
            elif r_level == "medium":
                med_cnt += 1
            else:
                low_cnt += 1

            # Check if matches filter
            if risk_level_filter and risk_level_filter.lower() != "all" and r_level != risk_level_filter.lower():
                continue

            factors = cls.generate_risk_factors(
                lead_time_days=feats["lead_time_days"],
                day_of_week=feats["day_of_week"],
                slot_hour=feats["slot_hour"],
                is_weekend=feats["is_weekend"],
                prior_appointments=feats["patient_prior_appointments"],
                prior_no_shows=feats["patient_prior_no_shows"],
                has_notes=feats["has_notes"],
                consultation_fee=feats["consultation_fee"],
            )

            pat_name = appt.patient.full_name if appt.patient else "Patient"
            pat_phone = appt.patient.phone if appt.patient else None

            scored_items.append(
                DoctorAppointmentRiskItem(
                    appointment_id=appt.id,
                    appointment_token=appt.appointment_token,
                    patient_id=appt.patient_id,
                    patient_name=pat_name,
                    patient_phone=pat_phone,
                    appointment_date=appt.appointment_date,
                    appointment_time=appt.appointment_time,
                    status=appt.status,
                    notes=appt.notes,
                    no_show_probability=prob,
                    risk_level=r_level,
                    risk_display_label=r_label,
                    reminder_recommended=rem_rec,
                    suggested_action=action,
                    top_factors=[f.description for f in factors[:2]],
                )
            )

        total_appts = len(all_appts)
        avg_risk = round(total_prob / total_appts, 4) if total_appts > 0 else 0.0

        # Paginate scored items
        offset = (page - 1) * page_size
        paginated_items = scored_items[offset : offset + page_size]

        return DoctorAppointmentsRiskListResponse(
            doctor_id=doctor_id,
            total_appointments=total_appts,
            high_risk_count=high_cnt,
            medium_risk_count=med_cnt,
            low_risk_count=low_cnt,
            average_risk_probability=avg_risk,
            items=paginated_items,
        )

    @classmethod
    async def get_hospital_no_show_analytics(
        cls,
        hospital_id: uuid.UUID,
        db: AsyncSession,
    ) -> HospitalNoShowAnalyticsResponse:
        """
        Aggregates hospital-level attendance statistics and scheduled risk distributions.
        """
        # 1. Fetch hospital details
        hosp_res = await db.execute(select(Hospital).where(Hospital.id == hospital_id))
        hospital = hosp_res.scalar_one_or_none()
        hospital_name = hospital.name if hospital else "Hospital Clinic"

        # 2. Historical aggregate status counts
        status_q = select(
            Appointment.status,
            func.count(Appointment.id),
        ).where(
            Appointment.hospital_id == hospital_id,
        ).group_by(Appointment.status)

        status_res = await db.execute(status_q)
        status_counts = dict(status_res.all())

        attended = status_counts.get("completed", 0)
        missed = status_counts.get("no_show", 0)
        total_hist = attended + missed
        no_show_rate = round(missed / total_hist, 4) if total_hist > 0 else 0.0

        # 3. Upcoming scheduled appointments risk distribution
        sched_q = (
            select(Appointment)
            .where(
                and_(
                    Appointment.hospital_id == hospital_id,
                    Appointment.status.in_(["scheduled", "checked_in"]),
                )
            )
            .options(
                selectinload(Appointment.doctor),
                selectinload(Appointment.patient),
            )
            .limit(200)
        )
        sched_res = await db.execute(sched_q)
        sched_appts = sched_res.scalars().all()

        low_c = 0
        med_c = 0
        high_c = 0
        for appt in sched_appts:
            feats = await cls.extract_appointment_features(appt, db)
            ml_req = NoShowPredictionRequest(**feats)
            ml_out = ml_prediction_service.predict_no_show(ml_req)
            r_level, _ = cls.classify_risk(ml_out.no_show_probability)
            if r_level == "high":
                high_c += 1
            elif r_level == "medium":
                med_c += 1
            else:
                low_c += 1

        total_sched = len(sched_appts)
        risk_dist = RiskDistributionSummary(
            low_risk_count=low_c,
            low_risk_percentage=round((low_c / total_sched) * 100, 1) if total_sched > 0 else 0.0,
            medium_risk_count=med_c,
            medium_risk_percentage=round((med_c / total_sched) * 100, 1) if total_sched > 0 else 0.0,
            high_risk_count=high_c,
            high_risk_percentage=round((high_c / total_sched) * 100, 1) if total_sched > 0 else 0.0,
        )

        # 4. Specialty trends
        spec_q = (
            select(
                Doctor.specialty,
                func.count(Appointment.id).label("total"),
                func.count(Appointment.id).filter(Appointment.status == "no_show").label("no_shows"),
            )
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .where(
                and_(
                    Appointment.hospital_id == hospital_id,
                    Appointment.status.in_(["completed", "no_show"]),
                )
            )
            .group_by(Doctor.specialty)
        )
        spec_res = await db.execute(spec_q)
        spec_rows = spec_res.all()

        specialty_trends: List[SpecialtyNoShowTrend] = []
        for row in spec_rows:
            spec_tot = row.total
            spec_ns = row.no_shows
            spec_rate = round(spec_ns / spec_tot, 4) if spec_tot > 0 else 0.0
            specialty_trends.append(
                SpecialtyNoShowTrend(
                    specialty=row.specialty,
                    total_appointments=spec_tot,
                    no_show_count=spec_ns,
                    no_show_rate=spec_rate,
                )
            )

        return HospitalNoShowAnalyticsResponse(
            hospital_id=hospital_id,
            hospital_name=hospital_name,
            total_historical_appointments=total_hist,
            attended_appointments=attended,
            missed_appointments=missed,
            historical_no_show_rate=no_show_rate,
            scheduled_appointments_count=total_sched,
            risk_distribution=risk_dist,
            specialty_trends=specialty_trends,
            model_name="logistic_regression",
            is_synthetic_model=True,
        )

    @classmethod
    async def send_smart_reminder(
        cls,
        appointment_id: uuid.UUID,
        db: AsyncSession,
    ) -> SendReminderResponse:
        """
        Dispatches an intelligent, idempotent appointment reminder to the patient.
        Does NOT alter appointment dates, times, or statuses.
        """
        query = (
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(
                selectinload(Appointment.doctor).selectinload(Doctor.user),
                selectinload(Appointment.hospital),
                selectinload(Appointment.patient),
            )
        )
        res = await db.execute(query)
        appointment = res.scalar_one_or_none()
        if not appointment:
            raise ValueError("Appointment not found")

        doc_name = (
            appointment.doctor.user.full_name
            if appointment.doctor and appointment.doctor.user
            else "Doctor"
        )
        hosp_name = appointment.hospital.name if appointment.hospital else "MediSmart Healthcare Clinic"
        pat_name = appointment.patient.full_name if appointment.patient else "Patient"

        # Unique idempotent key prevents spam / repeated reminder triggers for the same appointment date
        idempotency_key = f"appt_reminder_{appointment.id}_{appointment.appointment_date}"

        msg = (
            f"Dear {pat_name}, this is a friendly reminder for your upcoming consultation with "
            f"Dr. {doc_name} at {hosp_name} on {appointment.appointment_date.strftime('%A, %b %d, %Y')} "
            f"at {appointment.appointment_time.strftime('%I:%M %p')}. "
            f"Reference Token: {appointment.appointment_token}. "
            f"Please arrive 10-15 minutes prior for registration."
        )

        notif_res = await notification_service.create_notification(
            db=db,
            user_id=appointment.patient_id,
            title="Appointment Reminder: Dr. " + doc_name,
            message=msg,
            category="appointment",
            event_type="appointment_reminder",
            urgency="high",
            idempotency_key=idempotency_key,
            metadata_json={
                "appointment_id": str(appointment.id),
                "appointment_token": appointment.appointment_token,
                "doctor_name": doc_name,
                "appointment_date": appointment.appointment_date.isoformat(),
                "appointment_time": appointment.appointment_time.isoformat(),
            },
            auto_commit=True,
        )

        return SendReminderResponse(
            appointment_id=appointment.id,
            notification_id=notif_res.notification.id if notif_res.notification else None,
            patient_id=appointment.patient_id,
            patient_name=pat_name,
            message=msg,
            is_duplicate=notif_res.is_duplicate,
            status="duplicate_suppressed" if notif_res.is_duplicate else "sent",
        )

