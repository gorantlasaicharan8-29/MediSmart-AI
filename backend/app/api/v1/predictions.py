"""
ML Prediction API Endpoints for MediSmart.

Exposes the centralized in-memory ML prediction service for:
1. Patient Waiting-Time Regression (POST /api/v1/predictions/waiting-time)
2. Appointment No-Show Classification (POST /api/v1/predictions/no-show)
3. Model Service Readiness Status (GET /api/v1/predictions/status)

Security & Safety:
- Protected with standard active-user authentication (get_current_active_user).
- Pure in-memory inference without database mutations or table joins.
- Sanitized error responses without internal filesystem paths or stack traces.
- Explicit disclosure that all predictions derive from synthetic simulation models.
"""
import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.ml import (
    NoShowPredictionRequest,
    NoShowPredictionResponse,
    WaitingTimePredictionRequest,
    WaitingTimePredictionResponse,
)
from app.schemas.queue_prediction import (
    DoctorQueueAnalyticsResponse,
    PatientQueuePredictionResponse,
)
from app.schemas.no_show import (
    AppointmentNoShowRiskResponse,
    DoctorAppointmentsRiskListResponse,
    HospitalNoShowAnalyticsResponse,
    SendReminderResponse,
)
from app.services.ml_prediction import (
    ModelArtifactNotFoundError,
    ModelInferenceError,
    ml_prediction_service,
)
from app.services.no_show_service import NoShowRiskService
from app.services.queue_waiting_time import QueueWaitingTimeService

logger = logging.getLogger("medismart.api.predictions")

router = APIRouter()


@router.post(
    "/waiting-time",
    response_model=WaitingTimePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict patient waiting time at check-in",
    description=(
        "Estimates elapsed minutes until consultation call based on clinical department, "
        "queue depth, doctor pacing, and arrival timing. Trained on synthetic simulation data."
    ),
)
async def predict_waiting_time(
    data: WaitingTimePredictionRequest,
    current_user: User = Depends(get_current_active_user),
) -> WaitingTimePredictionResponse:
    """
    Computes expected wait time in minutes for a patient arrival event.
    Delegates to the shared ML prediction service.
    """
    try:
        return ml_prediction_service.predict_waiting_time(data)
    except ModelArtifactNotFoundError as e:
        logger.error("Waiting-time model unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Waiting-time prediction model is temporarily unavailable.",
        ) from None
    except ModelInferenceError as e:
        logger.exception("Waiting-time prediction inference failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Waiting-time prediction calculation failed.",
        ) from None
    except Exception as e:
        logger.exception("Unexpected error in waiting-time prediction endpoint.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction.",
        ) from None


@router.post(
    "/no-show",
    response_model=NoShowPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict appointment no-show probability and risk band",
    description=(
        "Estimates probability of unexcused patient absence based on scheduling lead time, "
        "historical attendance, slot hour, and department. Trained on synthetic data."
    ),
)
async def predict_no_show(
    data: NoShowPredictionRequest,
    current_user: User = Depends(get_current_active_user),
) -> NoShowPredictionResponse:
    """
    Computes no-show probability and illustrative risk band for an appointment booking.
    Delegates to the shared ML prediction service.
    """
    try:
        return ml_prediction_service.predict_no_show(data)
    except ModelArtifactNotFoundError as e:
        logger.error("No-show model unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Appointment no-show prediction model is temporarily unavailable.",
        ) from None
    except ModelInferenceError as e:
        logger.exception("No-show prediction inference failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Appointment no-show prediction calculation failed.",
        ) from None
    except Exception as e:
        logger.exception("Unexpected error in no-show prediction endpoint.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction.",
        ) from None


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get ML prediction service and model status",
    description="Returns the initialization and availability status of all ML models.",
)
async def get_prediction_service_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Reports readiness and metadata for both ML models.
    """
    return ml_prediction_service.get_service_status()


@router.get(
    "/queue/my",
    response_model=PatientQueuePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated patient's real-time queue waiting-time prediction",
    description=(
        "Returns intelligent waiting-time prediction derived from live queue depth, "
        "active consultation elapsed time, doctor pacing, and XGBoost machine learning."
    ),
)
async def get_my_queue_prediction(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PatientQueuePredictionResponse:
    """
    Calculates live waiting-time prediction for the authenticated patient's active queue token.
    Patient-isolated: cannot query other patients' queue predictions.
    """
    prediction = await QueueWaitingTimeService.predict_for_patient_queue(
        patient_id=current_user.id,
        db=db,
    )
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active queue entry found for today.",
        )
    return prediction


@router.get(
    "/doctor/queue-analytics",
    response_model=DoctorQueueAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get real-time intelligent queue flow analytics for doctor dashboard",
    description=(
        "Provides real-time clinical queue analytics: active consultation timer, "
        "predicted wait times for all waiting patients, congestion classification, and clearing time."
    ),
)
async def get_doctor_queue_analytics(
    doctor_id: Optional[uuid.UUID] = Query(None, description="Doctor ID (for admins)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
) -> DoctorQueueAnalyticsResponse:
    """
    Retrieves queue analytics for clinical staff.
    Doctors are restricted to their own clinical profile; admins can specify doctor_id.
    """
    target_doctor_id: Optional[uuid.UUID] = None

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        target_doctor_id = doc_res.scalar_one_or_none()
        if not target_doctor_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found for this account.",
            )
    else:
        if not doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="doctor_id query parameter is required for administrative staff.",
            )
        target_doctor_id = doctor_id

    try:
        return await QueueWaitingTimeService.get_doctor_queue_analytics(
            doctor_id=target_doctor_id,
            db=db,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from None


# ---------------------------------------------------------------------------
# Phase 9.3: AI Appointment No-Show Prediction & Analytics Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/appointments/{appointment_id}/risk",
    response_model=AppointmentNoShowRiskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive no-show risk assessment for a specific appointment",
    description=(
        "Returns calibrated no-show probability, risk band (Low/Medium/High), "
        "contributing risk factors, and recommended follow-up actions. Role-isolated."
    ),
)
async def get_appointment_no_show_risk(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AppointmentNoShowRiskResponse:
    """
    Role-protected appointment no-show assessment:
    - Patients: may only view risk assessment for their own appointments.
    - Doctors: may only view appointments assigned to their doctor profile.
    - Hospital Admins: may only view appointments in their hospital.
    - System Admins: may view all.
    """
    # 1. Fetch appointment to verify access rights
    query = select(Appointment).where(Appointment.id == appointment_id)
    res = await db.execute(query)
    appointment = res.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    # 2. Strict Role-Based Isolation
    if current_user.role == "patient" and appointment.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You may only view your own appointment risk assessment.",
        )

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doctor_id = doc_res.scalar_one_or_none()
        if appointment.doctor_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only view appointments assigned to your profile.",
            )

    if current_user.role == "hospital_admin":
        if current_user.hospital_id and appointment.hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only view appointments for your assigned hospital.",
            )

    # 3. Compute risk assessment
    risk_assessment = await NoShowRiskService.predict_for_appointment(
        appointment_id=appointment_id,
        db=db,
    )
    if not risk_assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not generate risk assessment for this appointment.",
        )

    return risk_assessment


@router.get(
    "/doctor/appointments-risk",
    response_model=DoctorAppointmentsRiskListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get doctor's appointment list with attendance risk scoring and filters",
    description=(
        "Retrieves doctor's booked consultations with no-show probability, risk levels, "
        "and summary metrics. Supports date and risk level filtering (all, low, medium, high)."
    ),
)
async def get_doctor_appointments_risk(
    date_filter: Optional[date] = Query(None, alias="date", description="Filter by appointment date"),
    risk_level: Optional[str] = Query(None, description="Filter by risk tier: all, low, medium, high"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    doctor_id: Optional[uuid.UUID] = Query(None, description="Doctor ID (for admins)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
) -> DoctorAppointmentsRiskListResponse:
    """
    Doctor-scoped appointment attendance risk list.
    """
    target_doctor_id: Optional[uuid.UUID] = None

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        target_doctor_id = doc_res.scalar_one_or_none()
        if not target_doctor_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found for this account.",
            )
    else:
        if not doctor_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="doctor_id query parameter is required for administrative staff.",
            )
        target_doctor_id = doctor_id

    return await NoShowRiskService.get_doctor_appointments_risk_list(
        doctor_id=target_doctor_id,
        db=db,
        date_filter=date_filter,
        risk_level_filter=risk_level,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/hospital/no-show-analytics",
    response_model=HospitalNoShowAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get hospital-level aggregate no-show analytics and risk distribution",
    description=(
        "Returns total appointments, completed vs missed counts, historical no-show rate, "
        "upcoming scheduled risk tier distribution, and specialty-wise attendance trends."
    ),
)
async def get_hospital_no_show_analytics(
    hospital_id: Optional[uuid.UUID] = Query(None, description="Hospital ID (for system admins)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("hospital_admin", "system_admin")),
) -> HospitalNoShowAnalyticsResponse:
    """
    Hospital admin aggregate analytics endpoint.
    Hospital admins are scoped to their own hospital_id.
    """
    target_hospital_id: Optional[uuid.UUID] = None

    if current_user.role == "hospital_admin":
        if not current_user.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hospital administrator is not affiliated with any hospital.",
            )
        target_hospital_id = current_user.hospital_id
    else:
        # System Admin
        if hospital_id:
            target_hospital_id = hospital_id
        else:
            first_hosp = await db.execute(select(Hospital.id).limit(1))
            target_hospital_id = first_hosp.scalar_one_or_none()
            if not target_hospital_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No hospital records available in system.",
                )

    return await NoShowRiskService.get_hospital_no_show_analytics(
        hospital_id=target_hospital_id,
        db=db,
    )


@router.post(
    "/appointments/{appointment_id}/send-reminder",
    response_model=SendReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Send smart appointment reminder notification to patient",
    description=(
        "Dispatches an idempotent notification for medium- or high-risk appointments. "
        "Does not mutate appointment schedules or clinical data."
    ),
)
async def send_appointment_reminder(
    appointment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
) -> SendReminderResponse:
    """
    Dispatches a patient reminder for a scheduled appointment.
    Verifies that the doctor is assigned to the appointment or admin belongs to hospital.
    """
    query = select(Appointment).where(Appointment.id == appointment_id)
    res = await db.execute(query)
    appointment = res.scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doctor_id = doc_res.scalar_one_or_none()
        if appointment.doctor_id != doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only send reminders for appointments assigned to you.",
            )

    if current_user.role == "hospital_admin":
        if current_user.hospital_id and appointment.hospital_id != current_user.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only send reminders for appointments in your hospital.",
            )

    try:
        return await NoShowRiskService.send_smart_reminder(
            appointment_id=appointment_id,
            db=db,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from None


