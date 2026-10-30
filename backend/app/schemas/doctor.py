import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DoctorUserSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorHospitalSummary(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    state: str

    model_config = ConfigDict(from_attributes=True)


class DoctorBase(BaseModel):
    specialty: str = Field(..., min_length=2, max_length=100)
    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: int = Field(0, ge=0, le=70)
    consultation_fee: Optional[float] = Field(None, ge=0.0)
    is_available: bool = True
    credential_status: str = Field("pending_verification", max_length=50)
    bio: Optional[str] = None
    available_days: List[str] = Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])


class DoctorCreate(DoctorBase):
    hospital_id: uuid.UUID
    user_id: uuid.UUID


class DoctorUpdate(BaseModel):
    specialty: Optional[str] = Field(None, min_length=2, max_length=100)
    qualification: Optional[str] = Field(None, max_length=255)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    consultation_fee: Optional[float] = Field(None, ge=0.0)
    is_available: Optional[bool] = None
    credential_status: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = None
    available_days: Optional[List[str]] = None


class DoctorProfileSelfUpdate(BaseModel):
    bio: Optional[str] = None
    is_available: Optional[bool] = None
    available_days: Optional[List[str]] = None
    consultation_fee: Optional[float] = Field(None, ge=0.0)


class DoctorNextAppointmentSummary(BaseModel):
    id: uuid.UUID
    appointment_token: str
    appointment_date: date
    appointment_time: str
    patient_name: str
    status: str


class DoctorDashboardStatsResponse(BaseModel):
    doctor_id: uuid.UUID
    doctor_name: str
    today_appointments: int
    waiting_patients: int
    completed_consultations: int
    next_appointment: Optional[DoctorNextAppointmentSummary] = None
    queue_date: date


class DoctorResponse(DoctorBase):
    id: uuid.UUID
    user_id: uuid.UUID
    hospital_id: uuid.UUID
    user: Optional[DoctorUserSummary] = None
    hospital: Optional[DoctorHospitalSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorListResponse(BaseModel):
    items: List[DoctorResponse]
    total: int
    page: int
    page_size: int


class DoctorSlot(BaseModel):
    time: str  # "HH:MM" e.g., "09:00", "09:30"
    is_available: bool
    status: Optional[str] = "available"  # "available", "booked", "past", "unavailable"


class DoctorSlotsDayResponse(BaseModel):
    doctor_id: uuid.UUID
    date: date
    day_of_week: str
    is_working_day: bool
    slots: List[DoctorSlot]
