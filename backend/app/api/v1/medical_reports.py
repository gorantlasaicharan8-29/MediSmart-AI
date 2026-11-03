"""
REST API Endpoints for AI Medical Report Analysis & Intelligent Health Document Understanding.
Part of MediSmart AI Phase 12.0.
"""
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user, require_roles
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.medical_report import (
    ExtractedMedicalParameter,
    MedicalDocument,
    MedicalParameterCorrection,
    MedicalReportAnalysis,
    MedicalReportReview,
)
from app.models.user import User
from app.schemas.medical_report import (
    DoctorReviewRequest,
    DoctorReviewResponse,
    ExtractedParameterResponse,
    MedicalDocumentResponse,
    MedicalReportAnalysisResponse,
    MedicalReportSummaryResponse,
    ParameterCorrectionRequest,
    ParameterCorrectionResponse,
    ParameterTrendResponse,
    ReportComparisonResponse,
)
from app.services.clinical_audit_service import clinical_audit_service
from app.services.medical_report_service import medical_report_service

logger = logging.getLogger("medismart.api.medical_reports")

router = APIRouter()


def _get_client_network_info(request: Request):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


async def _verify_patient_access(
    patient_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> None:
    """
    Enforces strict ownership & clinical relationship verification:
    - Patient can only access their own records.
    - Doctor can only access patients with whom they have an active or past appointment.
    - Hospital Admin can only access patients treated at their hospital.
    """
    if current_user.role == "patient":
        if current_user.id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only access your own medical documents.",
            )
        return

    if current_user.role == "doctor":
        doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
        doctor_id = doc_res.scalar_one_or_none()
        if not doctor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Doctor profile not found.",
            )

        care_check = await db.execute(
            select(Appointment.id).where(
                and_(
                    Appointment.patient_id == patient_id,
                    Appointment.doctor_id == doctor_id,
                )
            ).limit(1)
        )
        if care_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patient is not under your clinical care.",
            )
        return

    if current_user.role == "hospital_admin":
        if not current_user.hospital_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Unaffiliated hospital administrator.",
            )
        hosp_check = await db.execute(
            select(Appointment.id).where(
                and_(
                    Appointment.patient_id == patient_id,
                    Appointment.hospital_id == current_user.hospital_id,
                )
            ).limit(1)
        )
        if hosp_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patient has no records at your hospital.",
            )
        return

    if current_user.role == "system_admin":
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: Insufficient privileges.",
    )


# ---------------------------------------------------------------------------
# 1. Document Upload
# ---------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=MedicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a medical PDF report for automated extraction and analysis",
)
async def upload_medical_report(
    request: Request,
    file: UploadFile = File(...),
    document_category: str = Form("Other Medical Reports"),
    patient_id: Optional[uuid.UUID] = Form(None),
    report_date: Optional[date] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Uploads, validates, stores and processes a patient medical document.
    """
    ip, ua = _get_client_network_info(request)

    # Determine target patient
    if current_user.role == "patient":
        target_patient_id = current_user.id
    else:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required when uploading on behalf of a patient.",
            )
        await _verify_patient_access(patient_id, current_user, db)
        target_patient_id = patient_id

    file_bytes = await file.read()
    try:
        doc = await medical_report_service.upload_and_save_document(
            patient_id=target_patient_id,
            uploader=current_user,
            original_filename=file.filename or "medical_report.pdf",
            file_bytes=file_bytes,
            document_category=document_category,
            report_date=report_date,
            db=db,
        )
        await db.commit()
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))

    # Trigger synchronous analysis to immediately provide extracted results
    try:
        await medical_report_service.process_document(doc.id, db)
    except Exception as proc_err:
        logger.error(f"Error during initial processing of document {doc.id}: {proc_err}")

    # Clinical audit logging
    await clinical_audit_service.log(
        db=db,
        action="MEDICAL_DOCUMENT_UPLOAD",
        target_type="medical_document",
        actor=current_user,
        target_id=doc.id,
        patient_id=target_patient_id,
        metadata={
            "original_filename": doc.original_filename,
            "document_category": doc.document_category,
            "sha256_hash": doc.sha256_hash,
        },
        ip_address=ip,
        user_agent=ua,
    )

    # Refresh document
    await db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# 2. List Medical Documents
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[MedicalDocumentResponse],
    summary="List medical documents for current user or authorized patient",
)
async def list_medical_documents(
    patient_id: Optional[uuid.UUID] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == "patient":
        target_patient_id = current_user.id
    else:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for clinician and administrator queries.",
            )
        await _verify_patient_access(patient_id, current_user, db)
        target_patient_id = patient_id

    query = select(MedicalDocument).where(
        and_(
            MedicalDocument.patient_id == target_patient_id,
            MedicalDocument.is_deleted == False,
        )
    )
    if category:
        query = query.where(MedicalDocument.document_category == category)

    query = query.order_by(desc(MedicalDocument.report_date), desc(MedicalDocument.created_at))
    res = await db.execute(query)
    return res.scalars().all()


# ---------------------------------------------------------------------------
# 3. Document Details & Analysis
# ---------------------------------------------------------------------------
@router.get(
    "/{document_id}",
    response_model=MedicalDocumentResponse,
    summary="Get single medical document metadata",
)
async def get_medical_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(MedicalDocument).where(
        and_(
            MedicalDocument.id == document_id,
            MedicalDocument.is_deleted == False,
        )
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)
    return doc


@router.get(
    "/{document_id}/analysis",
    response_model=MedicalReportAnalysisResponse,
    summary="Get complete extraction analysis and parameters for a medical document",
)
async def get_document_analysis(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = (
        select(MedicalDocument)
        .where(
            and_(
                MedicalDocument.id == document_id,
                MedicalDocument.is_deleted == False,
            )
        )
        .options(
            selectinload(MedicalDocument.analyses).selectinload(MedicalReportAnalysis.parameters)
        )
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    if not doc.analyses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document analysis not found or processing is still pending.",
        )

    return doc.analyses[0]


@router.get(
    "/{document_id}/parameters",
    response_model=List[ExtractedParameterResponse],
    summary="Get extracted medical parameters for a document",
)
async def get_document_parameters(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    analysis_res = await get_document_analysis(document_id, db, current_user)
    return analysis_res.parameters


@router.get(
    "/{document_id}/summary",
    response_model=MedicalReportSummaryResponse,
    summary="Get structured plain-language report summary",
)
async def get_document_summary(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    analysis_res = await get_document_analysis(document_id, db, current_user)
    if not analysis_res.summary_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report summary is not available for this document.",
        )
    return analysis_res.summary_json


# ---------------------------------------------------------------------------
# 4. Secure File Download
# ---------------------------------------------------------------------------
@router.get(
    "/{document_id}/download",
    summary="Securely stream original PDF document file",
)
async def download_document(
    document_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ip, ua = _get_client_network_info(request)

    query = select(MedicalDocument).where(
        and_(
            MedicalDocument.id == document_id,
            MedicalDocument.is_deleted == False,
        )
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    physical_path = settings.MEDICAL_REPORTS_STORAGE_DIR / doc.stored_filename
    if not physical_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical file missing from storage.")

    # Audit download
    await clinical_audit_service.log(
        db=db,
        action="MEDICAL_DOCUMENT_DOWNLOAD",
        target_type="medical_document",
        actor=current_user,
        target_id=doc.id,
        patient_id=doc.patient_id,
        metadata={"filename": doc.original_filename},
        ip_address=ip,
        user_agent=ua,
    )

    return FileResponse(
        path=physical_path,
        media_type="application/pdf",
        filename=doc.original_filename,
    )


# ---------------------------------------------------------------------------
# 5. Reprocess Document
# ---------------------------------------------------------------------------
@router.post(
    "/{document_id}/reprocess",
    response_model=MedicalReportAnalysisResponse,
    summary="Trigger re-extraction and re-analysis of an existing document",
)
async def reprocess_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(MedicalDocument).where(
        and_(
            MedicalDocument.id == document_id,
            MedicalDocument.is_deleted == False,
        )
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    analysis = await medical_report_service.process_document(doc.id, db)
    return await get_document_analysis(doc.id, db, current_user)


# ---------------------------------------------------------------------------
# 6. Doctor Review & Parameter Correction
# ---------------------------------------------------------------------------
@router.post(
    "/{document_id}/review",
    response_model=DoctorReviewResponse,
    summary="Submit clinical physician review for a medical report",
)
async def submit_report_review(
    document_id: uuid.UUID,
    payload: DoctorReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
):
    ip, ua = _get_client_network_info(request)

    doc_res = await db.execute(select(MedicalDocument).where(MedicalDocument.id == document_id))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    review = await medical_report_service.submit_doctor_review(
        document_id=doc.id,
        doctor_user=current_user,
        review_status=payload.review_status,
        clinical_notes=payload.clinical_notes,
        db=db,
        ip_address=ip,
        user_agent=ua,
    )
    return review


@router.patch(
    "/{document_id}/parameters/{parameter_id}",
    response_model=ParameterCorrectionResponse,
    summary="Physician correction of an extracted parameter with immutable audit tracking",
)
async def correct_parameter(
    document_id: uuid.UUID,
    parameter_id: uuid.UUID,
    payload: ParameterCorrectionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "hospital_admin", "system_admin")),
):
    ip, ua = _get_client_network_info(request)

    doc_res = await db.execute(select(MedicalDocument).where(MedicalDocument.id == document_id))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    try:
        param = await medical_report_service.correct_extracted_parameter(
            parameter_id=parameter_id,
            doctor_user=current_user,
            corrected_value=payload.corrected_value,
            correction_reason=payload.correction_reason,
            db=db,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Retrieve newly recorded correction
    corr_res = await db.execute(
        select(MedicalParameterCorrection)
        .where(MedicalParameterCorrection.parameter_id == param.id)
        .order_by(desc(MedicalParameterCorrection.created_at))
        .limit(1)
    )
    corr = corr_res.scalar_one_or_none()
    return corr


# ---------------------------------------------------------------------------
# 7. Historical Report Comparison
# ---------------------------------------------------------------------------
@router.get(
    "/compare/reports",
    response_model=ReportComparisonResponse,
    summary="Compare two or more medical reports for the same patient",
)
async def compare_reports(
    document_ids: List[uuid.UUID] = Query(..., min_length=2),
    patient_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == "patient":
        target_patient_id = current_user.id
    else:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for clinician report comparison.",
            )
        await _verify_patient_access(patient_id, current_user, db)
        target_patient_id = patient_id

    try:
        comparison = await medical_report_service.compare_reports(
            document_ids=document_ids,
            patient_id=target_patient_id,
            db=db,
        )
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------------------------------------------------------------------------
# 8. Parameter Trends
# ---------------------------------------------------------------------------
@router.get(
    "/trends/parameter",
    response_model=ParameterTrendResponse,
    summary="Get historical time-series points for a specific parameter for Recharts",
)
async def get_parameter_trends(
    parameter_name: str = Query(..., min_length=1),
    patient_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role == "patient":
        target_patient_id = current_user.id
    else:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required for clinician trend queries.",
            )
        await _verify_patient_access(patient_id, current_user, db)
        target_patient_id = patient_id

    return await medical_report_service.get_parameter_trends(
        patient_id=target_patient_id,
        canonical_name=parameter_name,
        db=db,
    )


# ---------------------------------------------------------------------------
# 9. Soft Delete Document
# ---------------------------------------------------------------------------
@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a medical report document",
)
async def delete_medical_document(
    document_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ip, ua = _get_client_network_info(request)

    query = select(MedicalDocument).where(
        and_(
            MedicalDocument.id == document_id,
            MedicalDocument.is_deleted == False,
        )
    )
    res = await db.execute(query)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical document not found.")

    await _verify_patient_access(doc.patient_id, current_user, db)

    doc.is_deleted = True
    await clinical_audit_service.log(
        db=db,
        action="MEDICAL_DOCUMENT_DELETE",
        target_type="medical_document",
        actor=current_user,
        target_id=doc.id,
        patient_id=doc.patient_id,
        metadata={"filename": doc.original_filename},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
