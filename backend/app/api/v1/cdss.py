"""
Clinical Decision Support System (CDSS) API Endpoints for MediSmart AI.

Protected clinical endpoints for authorized clinicians:
- POST /api/v1/cdss/evaluate: Comprehensive clinical encounter evaluation (summary, completeness, Rx safety, guidelines).
- POST /api/v1/cdss/summarize-notes: Assistive note summarization and structured symptom breakdown.
- POST /api/v1/cdss/check-documentation: Documentation thoroughness and completeness audit.
- POST /api/v1/cdss/medication-safety: Drug-drug interaction, duplicate class, and instruction checks.
- GET  /api/v1/cdss/guidelines: Evidence-based clinical guidelines matching.
- GET  /api/v1/cdss/patient/{patient_id}/insights: Longitudinal patient medical history insights.
"""
import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.doctor import Doctor
from app.models.appointment import Appointment
from app.models.user import User
from app.schemas.cdss import (
    CDSSComprehensiveRequest,
    CDSSComprehensiveResponse,
    CDSSFeedbackInput,
    CDSSFeedbackResponse,
    CDSSSafetyDashboardResponse,
    CDSSSafetyEventAcknowledgeRequest,
    CDSSSafetyEventResponse,
    ClinicalGuidelineResponse,
    ClinicalNoteSummaryResponse,
    ContraindicationAlert,
    DocumentationCompletenessResponse,
    KnowledgeBaseMetadata,
    MedicationSafetyCheckRequest,
    MedicationSafetyCheckResponse,
    NoteSummaryInput,
    PatientHistoryInsightsResponse,
)
from app.services.cdss_service import cdss_service
from app.services.clinical_audit_service import clinical_audit_service

logger = logging.getLogger("medismart.api.cdss")

router = APIRouter()


def _get_network_info(request: Request):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post(
    "/evaluate",
    response_model=CDSSComprehensiveResponse,
    summary="Comprehensive clinical encounter evaluation for the doctor workspace",
)
async def evaluate_clinical_encounter(
    payload: CDSSComprehensiveRequest,
    request: Request,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluates an active doctor consultation encounter.
    Combines note summarization, completeness auditing, medication interaction checks,
    and clinical practice guideline retrieval in a single efficient call.
    """
    ip, ua = _get_network_info(request)
    return await cdss_service.evaluate_encounter(
        payload=payload,
        doctor_user=current_user,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/summarize-notes",
    response_model=ClinicalNoteSummaryResponse,
    summary="Generate concise structured summary from clinical encounter notes",
)
async def summarize_clinical_notes(
    notes: NoteSummaryInput,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
):
    """
    Generates an executive clinical summary and structures symptoms with source provenance.
    Never invents unrecorded patient information.
    """
    return cdss_service.summarize_clinical_notes(notes)


@router.post(
    "/check-documentation",
    response_model=DocumentationCompletenessResponse,
    summary="Audit clinical documentation completeness across medico-legal sections",
)
async def check_documentation_completeness(
    notes: NoteSummaryInput,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
):
    """
    Evaluates clinical documentation completeness, computes a score (0-100%),
    and generates actionable recommendations to ensure high-quality patient records.
    """
    return cdss_service.audit_documentation_completeness(notes)


@router.post(
    "/medication-safety",
    response_model=MedicationSafetyCheckResponse,
    summary="Audit prescribed medications for duplicates, verified interactions, and missing instructions",
)
async def check_medication_safety(
    payload: MedicationSafetyCheckRequest,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Cross-checks proposed medications against verified clinical pharmacology drug-drug
    interactions, duplicate pharmacological classes, and missing instruction fields.
    """
    pat_uuid: Optional[uuid.UUID] = None
    if payload.patient_id:
        try:
            pat_uuid = uuid.UUID(payload.patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient UUID format.")

    return await cdss_service.evaluate_medication_safety(
        current_items=payload.items,
        patient_id=pat_uuid,
        db=db,
    )


@router.get(
    "/guidelines",
    response_model=ClinicalGuidelineResponse,
    summary="Retrieve evidence-based clinical practice guidelines for documented condition",
)
async def get_clinical_guidelines(
    diagnosis: Optional[str] = Query(None, description="Clinical diagnosis or symptom description"),
    code: Optional[str] = Query(None, description="Standardized ICD-10 diagnosis code"),
    specialty: Optional[str] = Query(None, description="Physician clinical specialty"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Matches documented diagnoses with accredited clinical practice guidelines (ACC/AHA, NICE, ADA, GINA).
    Returns first-line therapies, lifestyle guidance, monitoring protocols, and red-flag referral triggers.
    """
    return cdss_service.match_clinical_guidelines(
        diagnosis_name=diagnosis,
        diagnosis_code=code,
        specialty=specialty,
    )


@router.get(
    "/patient/{patient_id}/insights",
    response_model=PatientHistoryInsightsResponse,
    summary="Retrieve longitudinal patient medical history insights for authorized clinicians",
)
async def get_patient_history_insights(
    patient_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Compiles longitudinal medical history (diagnoses, active prescriptions, chronic conditions)
    strictly for authorized treating physicians or administrators.
    """
    ip, ua = _get_network_info(request)

    if current_user.role == "doctor":
        # Verify doctor is treating or scheduled with this patient
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doctor_id = doc_res.scalar_one_or_none()
        if not doctor_id:
            raise HTTPException(status_code=403, detail="Doctor profile not found.")

        appt_check = await db.execute(
            select(Appointment.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.doctor_id == doctor_id,
            )
            .limit(1)
        )
        if appt_check.scalar_one_or_none() is None:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="patient_insights",
                actor=current_user,
                target_id=patient_id,
                metadata={"attempted_patient_id": str(patient_id)},
                ip_address=ip,
                user_agent=ua,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to view clinical insights for this patient.",
            )

    return await cdss_service.get_patient_history_insights(patient_id=patient_id, db=db)


@router.get(
    "/knowledge-base/metadata",
    response_model=KnowledgeBaseMetadata,
    summary="Retrieve clinical knowledge base governance metadata and version information",
)
async def get_knowledge_base_metadata(
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns governance metadata for the Clinical Decision Support System knowledge base,
    including version, review timestamps, active rule counts, and governance policy.
    """
    return cdss_service.get_knowledge_base_metadata()


@router.post(
    "/safety-events/acknowledge",
    response_model=CDSSSafetyEventResponse,
    summary="Acknowledge or dismiss a CDSS safety alert",
)
async def acknowledge_safety_event(
    payload: CDSSSafetyEventAcknowledgeRequest,
    request: Request,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Records clinician acknowledgement or dismissal of a CDSS safety alert.
    Requires doctor or administrator credentials.
    """
    ip, ua = _get_network_info(request)
    return await cdss_service.acknowledge_safety_event(
        doctor_user=current_user,
        payload=payload,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.post(
    "/feedback",
    response_model=CDSSFeedbackResponse,
    summary="Submit clinician feedback on CDSS recommendation accuracy",
)
async def submit_clinician_feedback(
    payload: CDSSFeedbackInput,
    request: Request,
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Captures clinician feedback on CDSS evaluation accuracy, guideline freshness,
    or interaction relevance for offline review by the clinical governance board.
    Does not autonomously modify knowledge base rules.
    """
    ip, ua = _get_network_info(request)
    return await cdss_service.record_clinician_feedback(
        doctor_user=current_user,
        payload=payload,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )


@router.get(
    "/feedback",
    response_model=list[CDSSFeedbackResponse],
    summary="Retrieve CDSS clinician feedback entries for audit and review",
)
async def get_clinician_feedback(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of feedback records to retrieve"),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves clinician feedback records for governance review and QA tracking.
    """
    return await cdss_service.get_clinician_feedback(
        user=current_user,
        db=db,
        limit=limit,
    )


@router.get(
    "/dashboard/metrics",
    response_model=CDSSSafetyDashboardResponse,
    summary="Retrieve CDSS safety metrics, alert resolution rates, and governance trends",
)
async def get_safety_dashboard_metrics(
    hospital_id: Optional[uuid.UUID] = Query(None, description="Filter metrics by hospital ID"),
    severity: Optional[str] = Query(None, description="Filter by warning severity (CRITICAL, HIGH, etc.)"),
    warning_category: Optional[str] = Query(None, description="Filter by warning category (DRUG_INTERACTION, CONTRAINDICATION, etc.)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns aggregated safety metrics, alert resolution rates, overdue guidelines,
    feedback summaries, and sanitized recent safety events (zero PHI).
    Accessible to authorized clinicians and administrators.
    """
    return await cdss_service.get_safety_dashboard_metrics(
        user=current_user,
        db=db,
        hospital_id=hospital_id,
        severity=severity,
        warning_category=warning_category,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/contraindications",
    response_model=list[ContraindicationAlert],
    summary="Retrieve verified absolute clinical contraindication rules catalog",
)
async def get_verified_contraindications(
    current_user: User = Depends(get_current_active_user),
):
    """
    Returns the catalog of accredited, validated absolute clinical contraindications
    tracked by the CDSS knowledge base.
    """
    return cdss_service.get_verified_contraindications()



