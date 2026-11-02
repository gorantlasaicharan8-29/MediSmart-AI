import uuid
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Diagnosis Schemas
# ---------------------------------------------------------------------------

class DiagnosisCreate(BaseModel):
    """Physician input to record a clinician-entered diagnosis."""
    diagnosis_name: str = Field(..., min_length=2, max_length=255, description="Primary clinical diagnosis name")
    clinical_description: Optional[str] = Field(None, max_length=2000, description="Detailed diagnostic notes")
    diagnosis_code: Optional[str] = Field(None, max_length=50, description="Optional standardized code (e.g. ICD-10)")
    status: str = Field("active", max_length=30, description="Diagnosis status: active, resolved, chronic")


class DiagnosisResponse(BaseModel):
    """Structured diagnosis response."""
    id: uuid.UUID
    consultation_note_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    diagnosis_name: str
    clinical_description: Optional[str] = None
    diagnosis_code: Optional[str] = None
    diagnosis_date: date
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Prescription Item & Prescription Schemas
# ---------------------------------------------------------------------------

class PrescriptionItemCreate(BaseModel):
    """Individual prescribed medication line."""
    medication_name: str = Field(..., min_length=1, max_length=255, description="Medication brand or generic name")
    dosage: str = Field(..., min_length=1, max_length=100, description="Dosage (e.g., 500mg, 10ml)")
    frequency: str = Field(..., min_length=1, max_length=100, description="Frequency (e.g., Twice daily after meals)")
    duration: str = Field(..., min_length=1, max_length=100, description="Duration (e.g., 5 days, 1 month)")
    route: str = Field("Oral", max_length=50, description="Route: Oral, Topical, Inhalation, Intravenous, etc.")
    instructions: Optional[str] = Field(None, max_length=1000, description="Specific patient administration advice")


class PrescriptionItemResponse(BaseModel):
    """Prescription item detail response."""
    id: uuid.UUID
    prescription_id: uuid.UUID
    medication_name: str
    dosage: str
    frequency: str
    duration: str
    route: str
    instructions: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescriptionCreate(BaseModel):
    """Input payload to issue a digital prescription."""
    notes: Optional[str] = Field(None, max_length=2000, description="General prescription advice or precautions")
    items: List[PrescriptionItemCreate] = Field(..., min_length=1, description="List of prescribed medications")


class PrescriptionResponse(BaseModel):
    """Complete digital prescription record."""
    id: uuid.UUID
    prescription_number: str
    consultation_note_id: uuid.UUID
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: Optional[str] = None
    doctor_id: uuid.UUID
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    hospital_id: uuid.UUID
    hospital_name: Optional[str] = None
    prescription_date: date
    notes: Optional[str] = None
    is_active: bool
    version: int = 1
    amendment_reason: Optional[str] = None
    superseded_by_id: Optional[uuid.UUID] = None
    items: List[PrescriptionItemResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescriptionAmendRequest(BaseModel):
    """Doctor request to amend or revise an existing digital prescription."""
    amendment_reason: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Clinical rationale for amending medication, dosage, or frequency",
    )
    notes: Optional[str] = Field(None, max_length=2000, description="Updated dispensing notes or advice")
    items: List[PrescriptionItemCreate] = Field(..., min_length=1, description="Amended medication list")


# ---------------------------------------------------------------------------
# Clinical Consultation Note Schemas
# ---------------------------------------------------------------------------

class ConsultationNoteCreate(BaseModel):
    """Doctor clinical documentation input."""
    appointment_id: uuid.UUID
    chief_complaint: str = Field(..., min_length=3, max_length=2000, description="Primary patient complaint")
    symptoms: Optional[str] = Field(None, max_length=4000, description="Reported clinical symptoms")
    clinical_observations: Optional[str] = Field(None, max_length=4000, description="Objective physician observations")
    examination_notes: Optional[str] = Field(None, max_length=4000, description="Physical examination notes")
    diagnosis_summary: str = Field(..., min_length=3, max_length=2000, description="Primary clinical diagnostic impression")
    treatment_plan: str = Field(..., min_length=3, max_length=4000, description="Comprehensive management and therapy plan")
    doctor_recommendations: Optional[str] = Field(None, max_length=2000, description="Diet, lifestyle, and recovery advice")

    follow_up_recommended_date: Optional[date] = Field(None, description="Recommended next consultation date")
    follow_up_instructions: Optional[str] = Field(None, max_length=1000, description="Instructions for follow-up care")

    diagnoses: Optional[List[DiagnosisCreate]] = Field(default_factory=list, description="Structured diagnosis entries")
    prescription: Optional[PrescriptionCreate] = Field(None, description="Optional digital prescription to issue")


class ConsultationNoteResponse(BaseModel):
    """Complete clinical consultation record."""
    id: uuid.UUID
    appointment_id: uuid.UUID
    appointment_token: Optional[str] = None
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    doctor_specialty: str
    hospital_id: uuid.UUID
    hospital_name: str
    consultation_date: date
    consultation_time: time

    chief_complaint: str
    symptoms: Optional[str] = None
    clinical_observations: Optional[str] = None
    examination_notes: Optional[str] = None
    diagnosis_summary: str
    treatment_plan: str
    doctor_recommendations: Optional[str] = None

    follow_up_recommended_date: Optional[date] = None
    follow_up_instructions: Optional[str] = None

    diagnoses: List[DiagnosisResponse] = Field(default_factory=list)
    prescriptions: List[PrescriptionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Follow-Up & Patient Medical History Schemas
# ---------------------------------------------------------------------------

class FollowUpCreateRequest(BaseModel):
    """Doctor request to recommend follow-up and optionally schedule appointment."""
    appointment_id: uuid.UUID
    recommended_date: date
    recommended_time: Optional[str] = Field("10:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    instructions: Optional[str] = Field(None, max_length=1000)
    schedule_appointment: bool = Field(False, description="Whether to immediately book a follow-up slot")


class FollowUpResponse(BaseModel):
    """Response following follow-up recommendation or appointment creation."""
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    recommended_date: date
    instructions: Optional[str] = None
    follow_up_appointment_id: Optional[uuid.UUID] = None
    follow_up_token: Optional[str] = None
    notification_dispatched: bool
    status: str


class PatientMedicalHistoryResponse(BaseModel):
    """Comprehensive electronic health record (EHR) timeline for a patient."""
    patient_id: uuid.UUID
    patient_name: str
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    total_consultations: int
    total_prescriptions: int
    active_diagnoses_count: int
    consultations: List[ConsultationNoteResponse]
    prescriptions: List[PrescriptionResponse]
    diagnoses: List[DiagnosisResponse]
    upcoming_follow_ups: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Clinical Audit Log Schemas
# ---------------------------------------------------------------------------

class ClinicalAuditLogResponse(BaseModel):
    """Sanitized clinical audit log record."""
    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_role: str
    actor_email: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[uuid.UUID] = None
    patient_id: Optional[uuid.UUID] = None
    doctor_id: Optional[uuid.UUID] = None
    hospital_id: Optional[uuid.UUID] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalAuditLogListResponse(BaseModel):
    """Paginated list of clinical audit events."""
    items: List[ClinicalAuditLogResponse]
    total: int

