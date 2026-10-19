import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QueueCheckInRequest(BaseModel):
    """Payload for patient or staff check-in."""
    appointment_token: Optional[str] = Field(None, description="Appointment token (e.g. MS-20261019-A1B2)")
    appointment_id: Optional[uuid.UUID] = Field(None, description="Direct appointment UUID")


class QueueActionRequest(BaseModel):
    """Payload for clinical queue status actions."""
    notes: Optional[str] = Field(None, max_length=1000, description="Optional clinical/reception annotations")


class QueuePublicItem(BaseModel):
    """Anonymized queue item for public waiting-room monitors (strictly zero PII)."""
    token_display: str
    token_number: int
    position: int
    status: str
    estimated_wait_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class QueuePublicBoardResponse(BaseModel):
    """Publicly accessible waiting room monitor data with zero patient PII."""
    doctor_id: uuid.UUID
    doctor_name: str
    specialty: str
    hospital_name: str
    queue_date: date
    current_consultation: Optional[QueuePublicItem] = None
    waiting_list: List[QueuePublicItem]
    total_waiting: int


class QueueEntryResponse(BaseModel):
    """Patient queue status response."""
    id: uuid.UUID
    appointment_id: uuid.UUID
    hospital_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    queue_date: date
    token_number: int
    token_display: str
    position: int
    status: str
    estimated_wait_minutes: Optional[int] = None
    notes: Optional[str] = None
    checked_in_at: datetime
    called_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorQueueItemResponse(BaseModel):
    """Detailed queue entry item for authorized clinical doctor/staff view."""
    id: uuid.UUID
    token_number: int
    token_display: str
    position: int
    status: str
    patient_id: uuid.UUID
    patient_name: str
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    appointment_id: uuid.UUID
    appointment_token: str
    appointment_time: str
    checked_in_at: datetime
    called_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorQueueResponse(BaseModel):
    """Full authenticated clinical queue view for doctors and hospital admins."""
    doctor_id: uuid.UUID
    doctor_name: str
    specialty: str
    hospital_id: uuid.UUID
    hospital_name: str
    queue_date: date
    current_consultation: Optional[DoctorQueueItemResponse] = None
    waiting_list: List[DoctorQueueItemResponse]
    total_waiting: int
    total_completed: int
    total_skipped: int
