import uuid
from datetime import date, time
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Date, ForeignKey, Index, String, Text, Time, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.queue import QueueEntry


class Appointment(Base, UUIDMixin, TimestampMixin):
    """Appointment booking model."""
    __tablename__ = "appointments"

    __table_args__ = (
        Index(
            "uq_active_doctor_slot",
            "doctor_id",
            "appointment_date",
            "appointment_time",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )

    appointment_token: Mapped[str] = mapped_column(
        String(50),
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
    appointment_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="scheduled",
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    patient: Mapped["User"] = relationship("User", back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="appointments")
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="appointments")
    queue_entry: Mapped[Optional["QueueEntry"]] = relationship(
        "QueueEntry",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )
