import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.user import User


class QueueEntry(Base, UUIDMixin, TimestampMixin):
    """Digital queue token and waiting state model."""
    __tablename__ = "queue_entries"

    __table_args__ = (
        # Enforce that a doctor can have at most one patient in consultation on a given clinic date
        Index(
            "uq_active_doctor_in_consultation",
            "doctor_id",
            "queue_date",
            unique=True,
            postgresql_where=text("status = 'in_consultation'"),
        ),
        # Enforce daily token number uniqueness per doctor and clinic date
        UniqueConstraint(
            "doctor_id",
            "queue_date",
            "token_number",
            name="uq_doctor_date_token_number",
        ),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    queue_date: Mapped[date] = mapped_column(
        Date,
        server_default=func.current_date(),
        index=True,
        nullable=False,
    )
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="waiting",
        nullable=False,
    )
    estimated_wait_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    called_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def token_display(self) -> str:
        """Formatted display token (e.g. Q-001). Computed dynamically to maintain single source of truth."""
        return f"Q-{self.token_number:03d}"

    # Relationships
    appointment: Mapped["Appointment"] = relationship(
        "Appointment",
        back_populates="queue_entry",
    )
    hospital: Mapped["Hospital"] = relationship(
        "Hospital",
        back_populates="queue_entries",
    )
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        back_populates="queue_entries",
    )
    patient: Mapped["User"] = relationship(
        "User",
        back_populates="queue_entries",
    )

