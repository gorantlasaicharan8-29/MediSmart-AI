"""
Pydantic v2 Request and Response Schemas for AI Medical Report Analysis.
Part of MediSmart AI Phase 12.0.
"""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtractedParameterResponse(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    parameter_name: str
    canonical_name: str
    category: str
    extracted_value: str
    numeric_value: Optional[float] = None
    original_unit: Optional[str] = None
    canonical_unit: Optional[str] = None
    reference_range_text: Optional[str] = None
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    range_status: str
    is_critical: bool
    extraction_confidence: float
    source_page: int
    source_text_snippet: Optional[str] = None
    verification_status: str

    model_config = ConfigDict(from_attributes=True)


class MedicalDocumentResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    document_category: str
    confirmed_category: Optional[str] = None
    report_date: Optional[date] = None
    processing_status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalReportAnalysisResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    extraction_engine_version: str
    analysis_status: str
    total_pages: int
    ocr_applied_pages: int
    raw_text_preview: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    extraction_metadata: Optional[Dict[str, Any]] = None
    parameters: List[ExtractedParameterResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicalReportSummaryResponse(BaseModel):
    report_overview: str
    report_category: str
    report_date: str
    total_parameters_extracted: int
    parameters_within_range_count: int
    parameters_below_range_count: int
    parameters_above_range_count: int
    parameters_requiring_verification_count: int
    critical_alerts_count: int
    below_range_parameters: List[str] = Field(default_factory=list)
    above_range_parameters: List[str] = Field(default_factory=list)
    critical_parameters: List[str] = Field(default_factory=list)
    important_observations: List[str] = Field(default_factory=list)
    doctor_review_status: str
    disclaimer: str


class DoctorReviewRequest(BaseModel):
    review_status: str = Field("REVIEWED", description="REVIEWED | CORRECTIONS_MADE | REPEAT_TEST_RECOMMENDED")
    clinical_notes: Optional[str] = Field(None, max_length=2000, description="Physician clinical notes or guidance")


class DoctorReviewResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    doctor_user_id: Optional[uuid.UUID] = None
    review_status: str
    clinical_notes: Optional[str] = None
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParameterCorrectionRequest(BaseModel):
    corrected_value: str = Field(..., min_length=1, max_length=100, description="Corrected lab measurement value")
    correction_reason: str = Field(..., min_length=3, max_length=1000, description="Clinical reason for correcting extraction")


class ParameterCorrectionResponse(BaseModel):
    id: uuid.UUID
    parameter_id: uuid.UUID
    prior_value: str
    corrected_value: str
    prior_range_status: str
    corrected_range_status: str
    correction_reason: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComparedParameterItem(BaseModel):
    canonical_name: str
    status: str
    history: List[Dict[str, Any]]
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    unit: Optional[str] = None
    delta: Optional[float] = None
    percent_change: Optional[float] = None
    trend: str
    unit_compatible: bool
    note: Optional[str] = None


class ReportComparisonResponse(BaseModel):
    patient_id: str
    reports_compared: List[Dict[str, Any]]
    total_compared_parameters: int
    parameters: List[ComparedParameterItem]
    disclaimer: str


class TrendDataPoint(BaseModel):
    date: str
    value: Optional[float] = None
    value_str: str
    unit: Optional[str] = None
    range_status: str
    is_critical: bool
    document_id: str
    filename: str


class ParameterTrendResponse(BaseModel):
    patient_id: str
    parameter_name: str
    unit: str
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    data_points: List[TrendDataPoint]
    total_records: int

