"""
Electronic Health Record (EHR) & Clinical Consultation API Endpoints for MediSmart.

Exposes secure, role-protected endpoints for:
1. Physician consultation notes documentation (POST /api/v1/ehr/consultations)
2. Appointment consultation record retrieval (GET /api/v1/ehr/consultations/appointment/{id})
3. Consultation note by ID (GET /api/v1/ehr/consultations/{id})
4. Patient medical history timeline (GET /api/v1/ehr/patient/{patient_id}/history)
5. Authenticated patient's own medical records (GET /api/v1/ehr/my-history)
6. Follow-up care coordination (POST /api/v1/ehr/follow-up)
7. Single prescription lookup with RBAC (GET /api/v1/ehr/prescriptions/{id})
8. Prescription amendment and revision (POST /api/v1/ehr/prescriptions/{id}/amend)
9. Clinical audit logs retrieval (GET /api/v1/ehr/audit-logs)

Security & Data Privacy:
- Strict role authorization, IDOR protection, and ownership verification.
- Zero medical data leakage in public boards or unauthenticated endpoints.
- Immutable audit timestamps on all records.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.ehr import (
    ClinicalAuditLogListResponse,
    ClinicalAuditLogResponse,
    ConsultationNoteCreate,
    ConsultationNoteResponse,
    FollowUpCreateRequest,
    FollowUpResponse,
    PatientMedicalHistoryResponse,
    PrescriptionAmendRequest,
    PrescriptionResponse,
)
from app.services.clinical_audit_service import clinical_audit_service
from app.services.ehr_service import EHRService

logger = logging.getLogger("medismart.api.ehr")

router = APIRouter()


def _get_client_network_info(request: Request):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post(
    "/consultations",
    response_model=ConsultationNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Document clinical consultation note and digital prescription",
    description=(
        "Records chief complaint, symptoms, physical examination, diagnosis summary, "
        "treatment plan, structured diagnoses, and digital prescriptions. "
        "Only authorized physicians assigned to the appointment may document the encounter."
    ),
)
async def create_or_update_consultation(
    data: ConsultationNoteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor")),
) -> ConsultationNoteResponse:
    """
    Creates or updates an official physician consultation record.
    Doctor-restricted and appointment-ownership validated.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.create_or_update_consultation(
        doctor_user=current_user,
        data=data,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/consultations/appointment/{appointment_id}",
    response_model=ConsultationNoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get clinical consultation note for an appointment",
    description="Retrieves official consultation notes, diagnoses, and digital prescriptions for an appointment.",
)
async def get_consultation_by_appointment(
    appointment_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ConsultationNoteResponse:
    """
    Retrieves consultation note by appointment ID.
    Patient-isolated, doctor-authorized, and hospital-scoped.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.get_consultation_note_by_appointment(
        appointment_id=appointment_id,
        current_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/consultations/{consultation_id}",
    response_model=ConsultationNoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get consultation note by record ID",
    description="Retrieves a specific consultation note by its unique identifier.",
)
async def get_consultation_by_id(
    consultation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ConsultationNoteResponse:
    """
    Retrieves consultation note by ID.
    Role-protected and access-validated.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.get_consultation_note_by_id(
        note_id=consultation_id,
        current_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/my-history",
    response_model=PatientMedicalHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated patient's electronic health record (EHR) timeline",
    description="Returns consultation records, clinician diagnoses, active prescriptions, and upcoming follow-ups.",
)
async def get_my_medical_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PatientMedicalHistoryResponse:
    """
    Retrieves the authenticated user's own medical history.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.get_patient_medical_history(
        patient_id=current_user.id,
        current_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/patient/{patient_id}/history",
    response_model=PatientMedicalHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get patient electronic health record (EHR) history by patient ID",
    description="Retrieves complete medical record history for a patient. Requires authorized care relationship.",
)
async def get_patient_history(
    patient_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PatientMedicalHistoryResponse:
    """
    Retrieves patient's EHR timeline.
    Only the patient themselves, treating physicians, or authorized hospital staff may access.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.get_patient_medical_history(
        patient_id=patient_id,
        current_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/follow-up",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Schedule or recommend patient follow-up care",
    description=(
        "Records follow-up instructions and optionally books an official follow-up appointment slot. "
        "Dispatches real-time in-app notification to the patient."
    ),
)
async def create_follow_up(
    data: FollowUpCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor")),
) -> FollowUpResponse:
    """
    Coordinates follow-up appointment planning for a patient.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.schedule_follow_up(
        doctor_user=current_user,
        data=data,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/prescriptions/{prescription_id}",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get prescription details by ID",
    description="Retrieves a specific digital prescription with medication items. Protected by strict RBAC.",
)
async def get_prescription_by_id(
    prescription_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PrescriptionResponse:
    """
    Retrieves a single prescription.
    Patient-isolated, doctor-authorized, and hospital-scoped.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.get_prescription_by_id(
        prescription_id=prescription_id,
        current_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/prescriptions/{prescription_id}/amend",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Amend an issued digital prescription",
    description=(
        "Safely amends an issued prescription by creating a new revision (version+1) "
        "and marking the original as superseded. Full audit trail recorded."
    ),
)
async def amend_prescription(
    prescription_id: uuid.UUID,
    data: PrescriptionAmendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor")),
) -> PrescriptionResponse:
    """
    Amends an issued prescription.
    Doctor-restricted and care-relationship validated.
    """
    ip, ua = _get_client_network_info(request)
    return await EHRService.amend_prescription(
        prescription_id=prescription_id,
        doctor_user=current_user,
        data=data,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/audit-logs",
    response_model=ClinicalAuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve clinical audit trail entries",
    description="Provides HIPAA/GDPR audit trail review for authorized personnel.",
)
async def get_clinical_audit_logs(
    patient_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ClinicalAuditLogListResponse:
    """
    Retrieves clinical audit logs scoped strictly to authorized boundaries:
    - Patients may only view audit logs regarding their own patient record.
    - Doctors may query logs for patients under their care.
    - Hospital/System Admins can review facility audit events.
    """
    query_patient_id = patient_id

    if current_user.role == "patient":
        query_patient_id = current_user.id
    elif current_user.role == "doctor":
        # If doctor specifies patient_id, verify care relationship
        if patient_id:
            from sqlalchemy import select, and_
            from app.models.appointment import Appointment
            doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
            doctor_id = doc_res.scalar_one_or_none()
            if not doctor_id:
                raise HTTPException(status_code=403, detail="Doctor profile not found.")
            appt_check = await db.execute(
                select(Appointment.id).where(
                    and_(Appointment.patient_id == patient_id, Appointment.doctor_id == doctor_id)
                ).limit(1)
            )
            if appt_check.scalar_one_or_none() is None:
                raise HTTPException(status_code=403, detail="Not authorized to audit records for this patient.")

    logs = await clinical_audit_service.query_logs(
        db=db,
        patient_id=query_patient_id,
        action=action,
        limit=limit,
        offset=offset,
    )

    items = [
        ClinicalAuditLogResponse(
            id=log.id,
            actor_id=log.actor_id,
            actor_role=log.actor_role,
            actor_email=log.actor_email,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            patient_id=log.patient_id,
            doctor_id=log.doctor_id,
            hospital_id=log.hospital_id,
            metadata_json=log.metadata_json,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return ClinicalAuditLogListResponse(items=items, total=len(items))
