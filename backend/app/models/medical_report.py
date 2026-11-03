"""
SQLAlchemy models for AI Medical Report Analysis & Intelligent Health Document Understanding.
Part of MediSmart AI Phase 12.0.
"""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class MedicalDocument(Base, UUIDMixin, TimestampMixin):
    """
    Represents an uploaded medical document (e.g., PDF lab report, diagnostic scan).
    Stores physical file metadata, SHA-256 for duplicate detection, and overall processing lifecycle state.
    """
    __tablename__ = "medical_documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/pdf")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    document_category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Other Medical Reports",
    )  # e.g., "Complete Blood Count (CBC)", "Lipid Profile", etc.
    confirmed_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )  # "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Relationships
    patient = relationship("User", foreign_keys=[patient_id], backref="medical_documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    analyses = relationship(
        "MedicalReportAnalysis",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(MedicalReportAnalysis.created_at)",
    )
    reviews = relationship(
        "MedicalReportReview",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="desc(MedicalReportReview.created_at)",
    )

    __table_args__ = (
        Index("ix_med_docs_patient_created", "patient_id", "created_at"),
        Index("ix_med_docs_patient_hash", "patient_id", "sha256_hash"),
    )


class MedicalReportAnalysis(Base, UUIDMixin, TimestampMixin):
    """
    Represents an extraction and analysis run for a medical document.
    Preserves engine version, OCR fallback flags, and raw extracted text preview.
    """
    __tablename__ = "medical_report_analyses"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    extraction_engine_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="12.0.0-pymupdf-rapidocr",
    )
    analysis_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="SUCCESS",
    )  # "SUCCESS" | "PARTIAL" | "FAILED"

    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ocr_applied_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_text_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    extraction_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    document = relationship("MedicalDocument", back_populates="analyses")
    parameters = relationship(
        "ExtractedMedicalParameter",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="ExtractedMedicalParameter.parameter_name",
    )


class ExtractedMedicalParameter(Base, UUIDMixin, TimestampMixin):
    """
    Represents an individual medical parameter extracted from the report.
    Strictly preserves original report names, original measurements, original units,
    and original laboratory-printed reference ranges.
    """
    __tablename__ = "extracted_medical_parameters"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_report_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    parameter_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="General")

    extracted_value: Mapped[str] = mapped_column(String(100), nullable=False)
    numeric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    original_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    canonical_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    reference_range_text: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    reference_range_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_range_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    range_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="REFERENCE_RANGE_NOT_AVAILABLE",
        index=True,
    )  # "WITHIN_RANGE" | "BELOW_RANGE" | "ABOVE_RANGE" | "CRITICAL_REVIEW_REQUIRED" | "REFERENCE_RANGE_NOT_AVAILABLE" | "EXTRACTION_REQUIRES_VERIFICATION"

    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.85)

    source_page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_text_snippet: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNVERIFIED",
    )  # "UNVERIFIED" | "DOCTOR_VERIFIED" | "DOCTOR_CORRECTED"

    # Relationships
    analysis = relationship("MedicalReportAnalysis", back_populates="parameters")
    corrections = relationship(
        "MedicalParameterCorrection",
        back_populates="parameter",
        cascade="all, delete-orphan",
        order_by="desc(MedicalParameterCorrection.created_at)",
    )


class MedicalParameterCorrection(Base, UUIDMixin):
    """
    Immutable audit record for physician corrections to an extracted parameter.
    Never overwrites original extraction without retaining exact prior values.
    """
    __tablename__ = "medical_parameter_corrections"

    parameter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_medical_parameters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    prior_value: Mapped[str] = mapped_column(String(100), nullable=False)
    corrected_value: Mapped[str] = mapped_column(String(100), nullable=False)
    prior_range_status: Mapped[str] = mapped_column(String(50), nullable=False)
    corrected_range_status: Mapped[str] = mapped_column(String(50), nullable=False)

    correction_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    parameter = relationship("ExtractedMedicalParameter", back_populates="corrections")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])


class MedicalReportReview(Base, UUIDMixin, TimestampMixin):
    """
    Clinical review submitted by an attending or authorized physician.
    Captures overall verification, clinical observations, and follow-up advice.
    """
    __tablename__ = "medical_report_reviews"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    review_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="REVIEWED",
    )  # "REVIEWED" | "CORRECTIONS_MADE" | "REPEAT_TEST_RECOMMENDED"

    clinical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    document = relationship("MedicalDocument", back_populates="reviews")
    doctor = relationship("Doctor", foreign_keys=[doctor_id])

