import uuid
from datetime import date, time
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.appointment import Appointment


class ConsultationNote(Base, UUIDMixin, TimestampMixin):
    """
    Clinical consultation record documented by an authorized physician.
    Enforces 1-to-1 relationship with a completed or in-progress Appointment.
    """
    __tablename__ = "consultation_notes"

    __table_args__ = (
        Index("ix_consultation_notes_patient_date", "patient_id", "consultation_date"),
        Index("ix_consultation_notes_doctor_date", "doctor_id", "consultation_date"),
        Index("ix_consultation_notes_hospital", "hospital_id"),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    consultation_date: Mapped[date] = mapped_column(Date, nullable=False)
    consultation_time: Mapped[time] = mapped_column(Time, nullable=False)

    # Clinical documentation fields
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clinical_observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    examination_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosis_summary: Mapped[str] = mapped_column(Text, nullable=False)
    treatment_plan: Mapped[str] = mapped_column(Text, nullable=False)
    doctor_recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Follow-up care planning
    follow_up_recommended_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    follow_up_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment",
        back_populates="consultation_note",
    )
    patient: Mapped["User"] = relationship("User", foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship("Doctor", foreign_keys=[doctor_id])
    hospital: Mapped["Hospital"] = relationship("Hospital", foreign_keys=[hospital_id])

    diagnoses: Mapped[List["Diagnosis"]] = relationship(
        "Diagnosis",
        back_populates="consultation_note",
        cascade="all, delete-orphan",
        order_by="Diagnosis.created_at",
    )
    prescriptions: Mapped[List["Prescription"]] = relationship(
        "Prescription",
        back_populates="consultation_note",
        cascade="all, delete-orphan",
        order_by="Prescription.created_at",
    )


class Diagnosis(Base, UUIDMixin, TimestampMixin):
    """
    Clinician-entered diagnosis record linked to a clinical consultation.
    Supports standardized diagnosis codes (e.g. ICD-10).
    """
    __tablename__ = "diagnoses"

    __table_args__ = (
        Index("ix_diagnoses_patient", "patient_id"),
        Index("ix_diagnoses_doctor", "doctor_id"),
    )

    consultation_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultation_notes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    diagnosis_name: Mapped[str] = mapped_column(String(255), nullable=False)
    clinical_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., ICD-10 code
    diagnosis_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)  # active, resolved, chronic

    # Relationships
    consultation_note: Mapped["ConsultationNote"] = relationship(
        "ConsultationNote",
        back_populates="diagnoses",
    )
    patient: Mapped["User"] = relationship("User", foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship("Doctor", foreign_keys=[doctor_id])


class Prescription(Base, UUIDMixin, TimestampMixin):
    """
    Official digital prescription issued by a licensed physician.
    Includes medication items, instructions, and audit timestamps.
    """
    __tablename__ = "prescriptions"

    __table_args__ = (
        Index("ix_prescriptions_patient", "patient_id"),
        Index("ix_prescriptions_doctor", "doctor_id"),
        Index("ix_prescriptions_hospital", "hospital_id"),
    )

    prescription_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    consultation_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultation_notes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    prescription_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    amendment_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    consultation_note: Mapped["ConsultationNote"] = relationship(
        "ConsultationNote",
        back_populates="prescriptions",
    )
    appointment: Mapped["Appointment"] = relationship("Appointment")
    patient: Mapped["User"] = relationship("User", foreign_keys=[patient_id])
    doctor: Mapped["Doctor"] = relationship("Doctor", foreign_keys=[doctor_id])
    hospital: Mapped["Hospital"] = relationship("Hospital", foreign_keys=[hospital_id])
    superseded_by: Mapped[Optional["Prescription"]] = relationship(
        "Prescription",
        remote_side="Prescription.id",
    )

    items: Mapped[List["PrescriptionItem"]] = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.created_at",
    )


class PrescriptionItem(Base, UUIDMixin, TimestampMixin):
    """
    Individual medication item within a digital prescription.
    """
    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "500mg"
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Twice daily after meals"
    duration: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "7 days"
    route: Mapped[str] = mapped_column(String(50), default="Oral", nullable=False)  # Oral, Topical, IV, etc.
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    prescription: Mapped["Prescription"] = relationship(
        "Prescription",
        back_populates="items",
    )


class ClinicalAuditLog(Base, UUIDMixin, TimestampMixin):
    """
    HIPAA/GDPR-compliant clinical audit trail for EHR interactions.
    Records actor, action, target entity, timestamp, and sanitized non-PHI metadata.
    """
    __tablename__ = "clinical_audit_logs"

    __table_args__ = (
        Index("ix_clinical_audit_actor_time", "actor_id", "created_at"),
        Index("ix_clinical_audit_patient_time", "patient_id", "created_at"),
        Index("ix_clinical_audit_action_time", "action", "created_at"),
        Index("ix_clinical_audit_target", "target_type", "target_id"),
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])
    patient: Mapped[Optional["User"]] = relationship("User", foreign_keys=[patient_id])
    doctor: Mapped[Optional["Doctor"]] = relationship("Doctor", foreign_keys=[doctor_id])
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", foreign_keys=[hospital_id])


