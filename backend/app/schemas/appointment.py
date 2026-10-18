import uuid
from datetime import date, datetime, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.doctor import DoctorHospitalSummary, DoctorResponse, DoctorUserSummary


class AppointmentCreate(BaseModel):
    doctor_id: uuid.UUID
    appointment_date: date
    appointment_time: str = Field(..., pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$", description="Time in HH:MM format")
    notes: Optional[str] = Field(None, max_length=1000)


class AppointmentCancelRequest(BaseModel):
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    appointment_token: str
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    hospital_id: uuid.UUID
    appointment_date: date
    appointment_time: time
    status: str
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    patient: Optional[DoctorUserSummary] = None
    doctor: Optional[DoctorResponse] = None
    hospital: Optional[DoctorHospitalSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentListResponse(BaseModel):
    items: List[AppointmentResponse]
    total: int
    page: int
    page_size: int
