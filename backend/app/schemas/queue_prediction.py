import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PatientQueuePredictionResponse(BaseModel):
    """
    Intelligent real-time waiting-time prediction response for authenticated patient.
    """
    queue_entry_id: uuid.UUID
    token_number: int
    token_display: str
    position: int
    patients_ahead: int
    estimated_wait_minutes: int = Field(..., ge=0, description="Rounded estimated wait time in minutes")
    predicted_wait_minutes_raw: float = Field(..., ge=0.0, description="Unrounded continuous prediction")
    display_wait_time: str = Field(..., description="Human-readable formatted wait time (e.g., '35 mins')")
    queue_status: str
    doctor_id: uuid.UUID
    doctor_name: str
    doctor_specialty: str
    hospital_name: str
    is_doctor_active_consultation: bool
    current_consultation_elapsed_minutes: Optional[float] = None
    historical_avg_consultation_minutes: float
    model_name: str = "xgboost"
    model_version: str = "1.0.0"
    is_fallback: bool = False
    prediction_timestamp: datetime
    explanation: str = "Your estimated waiting time is based on current queue activity and historical consultation durations."

    model_config = ConfigDict(from_attributes=True)


class DoctorQueueItemPrediction(BaseModel):
    """Queue entry with predicted wait time for doctor analytics."""
    queue_entry_id: uuid.UUID
    token_display: str
    token_number: int
    position: int
    patient_name: str
    appointment_time: Optional[str] = None
    predicted_wait_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class DoctorQueueAnalyticsResponse(BaseModel):
    """
    Intelligent real-time queue flow analytics for clinical doctor workspace.
    """
    doctor_id: uuid.UUID
    doctor_name: str
    specialty: str
    queue_date: date
    waiting_patients_count: int
    currently_consulting_token: Optional[str] = None
    current_consultation_elapsed_minutes: Optional[float] = None
    average_consultation_duration_minutes: float
    total_completed_today: int
    queue_congestion_status: str = Field(..., description="'low', 'moderate', 'high', or 'congested'")
    estimated_clearing_time_minutes: int = Field(..., description="Estimated time required to see all currently waiting patients")
    waiting_queue: List[DoctorQueueItemPrediction] = Field(default_factory=list)
    model_name: str = "xgboost"
    model_version: str = "1.0.0"
    prediction_timestamp: datetime
    analytics_summary: str

    model_config = ConfigDict(from_attributes=True)

