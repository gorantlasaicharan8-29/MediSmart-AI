from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.appointment import Appointment
    from app.models.queue import QueueEntry


class Hospital(Base, UUIDMixin, TimestampMixin):
    """Hospital facility model."""
    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Data provenance and attribution
    data_source: Mapped[str] = mapped_column(
        String(50),
        default="verified",
        server_default="verified",
        nullable=False,
    )
    source_attribution: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Specialties and facilities stored as PostgreSQL arrays of strings
    specialties: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    facilities: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    doctors: Mapped[List["Doctor"]] = relationship(
        "Doctor",
        back_populates="hospital",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[List["Appointment"]] = relationship(
        "Appointment",
        back_populates="hospital",
        cascade="all, delete-orphan",
    )
    queue_entries: Mapped[List["QueueEntry"]] = relationship(
        "QueueEntry",
        back_populates="hospital",
        cascade="all, delete-orphan",
    )
    # pyrefly: ignore[unknown-name]
    hospital_admins: Mapped[List["User"]] = relationship(
        "User",
        back_populates="hospital",
        foreign_keys="User.hospital_id",
    )

