import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.hospital import Hospital
    from app.models.doctor import Doctor
    from app.models.appointment import Appointment
    from app.models.queue import QueueEntry
    from app.models.notification import Notification


class User(Base, UUIDMixin, TimestampMixin):
    """User account model for patients, doctors, hospital admins, and system admins."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="patient")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Relationships
    hospital: Mapped[Optional["Hospital"]] = relationship(
        "Hospital",
        back_populates="hospital_admins",
        foreign_keys=[hospital_id],
    )
    doctor: Mapped[Optional["Doctor"]] = relationship(
        "Doctor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    queue_entries: Mapped[List["QueueEntry"]] = relationship(
        "QueueEntry",
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

