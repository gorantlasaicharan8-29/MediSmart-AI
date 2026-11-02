"""
SQLAlchemy models for CDSS Safety Monitoring and Clinician Feedback.
Part of Phase 11.2: Clinical Governance, Real-World Validation & Safety Monitoring.
"""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.user import User


class CDSSSafetyEvent(Base, UUIDMixin, TimestampMixin):
    """
    Structured safety-monitoring audit record for CDSS warnings.
    Tracks warning generation, clinical severity, category, acknowledgement,
    dismissal, reason for dismissal, and the knowledge-base version.
    Zero PHI stored.
    """
    __tablename__ = "cdss_safety_events"

    __table_args__ = (
        Index("ix_cdss_safety_doctor_time", "doctor_id", "created_at"),
        Index("ix_cdss_safety_appointment", "appointment_id"),
        Index("ix_cdss_safety_severity", "warning_severity"),
        Index("ix_cdss_safety_category", "warning_category"),
        Index("ix_cdss_safety_rule", "rule_identifier"),
        Index("ix_cdss_safety_hospital_action", "hospital_id", "action_taken"),
        Index("ix_cdss_safety_created_at", "created_at"),
    )

    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
    )

    kb_version: Mapped[str] = mapped_column(String(50), nullable=False)
    warning_category: Mapped[str] = mapped_column(String(50), nullable=False)  # DRUG_INTERACTION, DUPLICATE_THERAPY, ALLERGY_ALERT, CONTRADICTION
    warning_severity: Mapped[str] = mapped_column(String(30), nullable=False)  # CRITICAL, HIGH, MODERATE, INFORMATIONAL
    rule_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., DD-WAR-ASA, DD-ACE-SPI
    alert_summary: Mapped[str] = mapped_column(Text, nullable=False)

    action_taken: Mapped[str] = mapped_column(String(30), default="GENERATED", nullable=False)  # GENERATED, ACKNOWLEDGED, DISMISSED
    dismissal_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", foreign_keys=[appointment_id])
    doctor: Mapped[Optional["Doctor"]] = relationship("Doctor", foreign_keys=[doctor_id])
    patient: Mapped[Optional["User"]] = relationship("User", foreign_keys=[patient_id])
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", foreign_keys=[hospital_id])


class CDSSClinicianFeedback(Base, UUIDMixin, TimestampMixin):
    """
    Clinician feedback record for CDSS evaluation accuracy and clinical utility.
    Captures physician feedback on relevant, irrelevant, or incorrect alerts,
    guideline freshness, or missing interactions.
    Does not automatically mutate clinical rules.
    """
    __tablename__ = "cdss_clinician_feedback"

    __table_args__ = (
        Index("ix_cdss_feedback_doctor_time", "doctor_id", "created_at"),
        Index("ix_cdss_feedback_type", "feedback_type"),
        Index("ix_cdss_feedback_target", "target_type", "target_id"),
        Index("ix_cdss_feedback_status", "review_status"),
        Index("ix_cdss_feedback_created_at", "created_at"),
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )

    feedback_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # RELEVANT_ALERT, IRRELEVANT_ALERT, INCORRECT_ALERT, MISSING_INTERACTION, OUTDATED_GUIDELINE, INCORRECT_SYMPTOM_EXTRACTION, GENERAL_FEEDBACK

    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # interaction_rule, guideline, symptom_extraction, general
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kb_version: Mapped[str] = mapped_column(String(50), nullable=False)

    clinician_comment: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), default="PENDING_REVIEW", nullable=False)  # PENDING_REVIEW, UNDER_EVALUATION, ACCEPTED_FOR_UPDATE, REJECTED_CLINICALLY_INVALID
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", foreign_keys=[doctor_id])
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment", foreign_keys=[appointment_id])

