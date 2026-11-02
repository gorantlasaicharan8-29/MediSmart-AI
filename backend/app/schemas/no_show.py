import uuid
from datetime import date, time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RiskFactorExplanation(BaseModel):
    """Specific factor contributing to no-show prediction."""
    factor: str
    impact: str  # "increases_risk", "decreases_risk", "neutral"
    description: str


class AppointmentNoShowRiskResponse(BaseModel):
    """Detailed no-show risk assessment for a specific appointment."""
    appointment_id: uuid.UUID
    appointment_token: str
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    doctor_specialty: str
    hospital_name: str
    appointment_date: date
    appointment_time: time
    status: str
    
    # ML Prediction outputs
    no_show_probability: float = Field(..., ge=0.0, le=1.0)
    risk_level: str  # "low", "medium", "high"
    risk_display_label: str  # "Low Risk", "Medium Risk", "High Risk"
    predicted_no_show: int
    decision_threshold: float
    
    # Explainability & Suggested Actions
    risk_factors: List[RiskFactorExplanation]
    suggested_action: str
    reminder_recommended: bool
    
    # Feature values used
    features_used: Dict[str, Any]
    
    # Metadata & Transparency
    model_name: str = "logistic_regression"
    model_version: str = "1.0.0"
    is_synthetic_model: bool = True
    provenance_notice: str = (
        "Model trained on synthetic appointment records. "
        "Predictions are clinical decision-support indicators, not definitive diagnostics."
    )

    model_config = ConfigDict(from_attributes=True)


class DoctorAppointmentRiskItem(BaseModel):
    """Summary risk item for doctor appointments list."""
    appointment_id: uuid.UUID
    appointment_token: str
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: Optional[str] = None
    appointment_date: date
    appointment_time: time
    status: str
    notes: Optional[str] = None
    
    no_show_probability: float
    risk_level: str  # "low", "medium", "high"
    risk_display_label: str
    reminder_recommended: bool
    suggested_action: str
    top_factors: List[str]


class DoctorAppointmentsRiskListResponse(BaseModel):
    """Doctor workspace appointment risk list with summary metrics."""
    doctor_id: uuid.UUID
    total_appointments: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    average_risk_probability: float
    items: List[DoctorAppointmentRiskItem]


class SpecialtyNoShowTrend(BaseModel):
    """Specialty-wise appointment and no-show statistics."""
    specialty: str
    total_appointments: int
    no_show_count: int
    no_show_rate: float


class RiskDistributionSummary(BaseModel):
    """Distribution of risk tiers among upcoming scheduled appointments."""
    low_risk_count: int
    low_risk_percentage: float
    medium_risk_count: int
    medium_risk_percentage: float
    high_risk_count: int
    high_risk_percentage: float


class HospitalNoShowAnalyticsResponse(BaseModel):
    """Hospital administrator aggregate no-show analytics."""
    hospital_id: uuid.UUID
    hospital_name: str
    total_historical_appointments: int
    attended_appointments: int
    missed_appointments: int
    historical_no_show_rate: float
    scheduled_appointments_count: int
    risk_distribution: RiskDistributionSummary
    specialty_trends: List[SpecialtyNoShowTrend]
    model_name: str = "logistic_regression"
    is_synthetic_model: bool = True


class SendReminderResponse(BaseModel):
    """Response from sending a smart appointment reminder."""
    appointment_id: uuid.UUID
    notification_id: Optional[uuid.UUID] = None
    patient_id: uuid.UUID
    patient_name: str
    message: str
    is_duplicate: bool
    status: str

