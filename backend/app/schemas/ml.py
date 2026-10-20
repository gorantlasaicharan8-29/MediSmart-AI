"""
Pydantic schemas for MediSmart ML prediction service.

Validates input features for waiting-time regression and no-show classification models.
Defines transparent prediction response structures with synthetic provenance disclosures.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WaitingTimePredictionRequest(BaseModel):
    """
    Input features observable at patient check-in for waiting-time regression.
    """
    doctor_specialty: str = Field(
        ...,
        description="Doctor's clinical department (e.g. 'Cardiology', 'Pediatrics')",
        min_length=1,
        max_length=100,
    )
    doctor_experience_years: int = Field(
        ...,
        ge=0,
        le=70,
        description="Doctor seniority in years",
    )
    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday)",
    )
    slot_hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Scheduled appointment hour (0-23)",
    )
    slot_minute: int = Field(
        ...,
        ge=0,
        le=59,
        description="Scheduled appointment minute (0-59)",
    )
    arrival_lead_minutes: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Minutes arrived relative to scheduled slot (+ early, - late)",
    )
    queue_position_at_checkin: int = Field(
        ...,
        ge=1,
        le=1000,
        description="Assigned queue token position upon arrival (>= 1)",
    )
    patients_waiting_ahead: int = Field(
        ...,
        ge=0,
        le=1000,
        description="Number of waiting patients ahead in line (>= 0)",
    )
    is_doctor_active_consultation: int = Field(
        ...,
        ge=0,
        le=1,
        description="1 if doctor is currently with a patient, else 0",
    )
    historical_avg_consultation_minutes: float = Field(
        ...,
        gt=0.0,
        le=180.0,
        description="Doctor historical rolling baseline consultation duration in minutes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doctor_specialty": "Cardiology",
                "doctor_experience_years": 15,
                "day_of_week": 2,
                "slot_hour": 10,
                "slot_minute": 30,
                "arrival_lead_minutes": 10.0,
                "queue_position_at_checkin": 3,
                "patients_waiting_ahead": 2,
                "is_doctor_active_consultation": 1,
                "historical_avg_consultation_minutes": 18.0,
            }
        }
    )


class WaitingTimePredictionResponse(BaseModel):
    """
    Predicted waiting time output and model metadata.
    """
    predicted_wait_minutes: float = Field(
        ...,
        ge=0.0,
        description="Estimated elapsed wait time in minutes until doctor call (non-negative)",
    )
    unit: str = Field(
        "minutes",
        description="Unit of measurement for the predicted waiting time",
    )
    model_name: str = Field(
        "xgboost",
        description="Underlying ML model architecture",
    )
    model_version: str = Field(
        "1.0.0",
        description="ML pipeline artifact version",
    )
    prediction_source: str = Field(
        "ml_synthetic_model",
        description="Origin of the prediction output",
    )
    is_synthetic_model: bool = Field(
        True,
        description="Indicates whether the underlying model was trained on synthetic simulation data",
    )
    synthetic_notice: str = Field(
        "Trained exclusively on synthetic queue simulation data. Must not be represented as clinically calibrated observations.",
        description="Mandatory provenance and safety disclosure",
    )


class NoShowPredictionRequest(BaseModel):
    """
    Input features observable at booking time for appointment no-show classification.
    """
    doctor_specialty: str = Field(
        ...,
        description="Doctor's clinical department",
        min_length=1,
        max_length=100,
    )
    lead_time_days: int = Field(
        ...,
        ge=0,
        le=365,
        description="Days between booking creation date and appointment date",
    )
    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        description="Day of appointment (0=Monday, 6=Sunday)",
    )
    slot_hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Scheduled appointment hour (0-23)",
    )
    is_weekend: int = Field(
        ...,
        ge=0,
        le=1,
        description="1 if appointment is on Saturday or Sunday, else 0",
    )
    consultation_fee: float = Field(
        ...,
        ge=0.0,
        description="Doctor consultation fee in INR",
    )
    patient_prior_appointments: int = Field(
        ...,
        ge=0,
        description="Cumulative appointments booked prior to this appointment date",
    )
    patient_prior_no_shows: int = Field(
        ...,
        ge=0,
        description="Cumulative unexcused absences prior to this appointment date",
    )
    patient_prior_no_show_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Historical ratio of no-shows to prior appointments",
    )
    has_notes: int = Field(
        ...,
        ge=0,
        le=1,
        description="1 if patient added clinical notes during booking, else 0",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doctor_specialty": "Cardiology",
                "lead_time_days": 14,
                "day_of_week": 1,
                "slot_hour": 10,
                "is_weekend": 0,
                "consultation_fee": 1200.0,
                "patient_prior_appointments": 3,
                "patient_prior_no_shows": 1,
                "patient_prior_no_show_rate": 0.3333,
                "has_notes": 1,
            }
        }
    )


class NoShowPredictionResponse(BaseModel):
    """
    Predicted no-show probability, binary flag, risk band, and model metadata.
    """
    no_show_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated probability that patient will fail to attend (range [0.0, 1.0])",
    )
    predicted_no_show: int = Field(
        ...,
        ge=0,
        le=1,
        description="Binary prediction: 1 if probability exceeds decision threshold, else 0",
    )
    decision_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Operating classification threshold calibrated on validation split",
    )
    risk_band: str = Field(
        ...,
        description="Illustrative risk categorization: 'low', 'moderate', or 'high'",
    )
    risk_band_notice: str = Field(
        "Illustrative risk band for demonstration purposes only. Not clinically validated.",
        description="Clinical disclaimer for risk band categorization",
    )
    model_name: str = Field(
        "logistic_regression",
        description="Underlying ML model architecture",
    )
    model_version: str = Field(
        "1.0.0",
        description="ML pipeline artifact version",
    )
    prediction_source: str = Field(
        "ml_synthetic_model",
        description="Origin of the prediction output",
    )
    is_synthetic_model: bool = Field(
        True,
        description="Indicates whether the underlying model was trained on synthetic simulation data",
    )
    synthetic_notice: str = Field(
        "Trained exclusively on synthetic appointment data. Probabilities reflect synthetic behavior and must not be interpreted as validated clinical risk.",
        description="Mandatory provenance and safety disclosure",
    )
