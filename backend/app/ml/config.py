"""
ML Configuration & Feature Schema Definitions for MediSmart.
"""
from pathlib import Path
from typing import Dict, List

# Directory locations
ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
ARTIFACTS_DIR = ML_DIR / "artifacts"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# Dataset file paths
WAITING_TIME_DATASET_PATH = DATA_DIR / "waiting_time_dataset.csv"
NOSHOW_DATASET_PATH = DATA_DIR / "noshow_dataset.csv"

# Model artifact paths
WAITING_TIME_MODEL_PATH = ARTIFACTS_DIR / "waiting_time_pipeline.joblib"
WAITING_TIME_METRICS_PATH = ARTIFACTS_DIR / "waiting_time_metrics.json"
NOSHOW_MODEL_PATH = ARTIFACTS_DIR / "noshow_pipeline.joblib"
NOSHOW_METRICS_PATH = ARTIFACTS_DIR / "noshow_metrics.json"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

# Fixed default random seed for reproducibility
DEFAULT_RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Waiting-Time Regression Schema
# ---------------------------------------------------------------------------
WAITING_TIME_TARGET = "actual_wait_minutes"

WAITING_TIME_FEATURES: List[str] = [
    "doctor_specialty",
    "doctor_experience_years",
    "day_of_week",
    "slot_hour",
    "slot_minute",
    "arrival_lead_minutes",
    "queue_position_at_checkin",
    "patients_waiting_ahead",
    "is_doctor_active_consultation",
    "historical_avg_consultation_minutes",
]

WAITING_TIME_FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "doctor_specialty": {"type": "categorical", "description": "Clinical department", "unit": "category"},
    "doctor_experience_years": {"type": "integer", "description": "Doctor seniority in years", "unit": "years", "range": "[1, 40]"},
    "day_of_week": {"type": "integer", "description": "Day of week (0=Monday, 6=Sunday)", "unit": "day_index", "range": "[0, 6]"},
    "slot_hour": {"type": "integer", "description": "Scheduled appointment hour", "unit": "hour_24", "range": "[8, 18]"},
    "slot_minute": {"type": "integer", "description": "Scheduled appointment minute", "unit": "minutes", "range": "{0, 30}"},
    "arrival_lead_minutes": {"type": "float", "description": "Minutes arrived before scheduled slot (+ early, - late)", "unit": "minutes"},
    "queue_position_at_checkin": {"type": "integer", "description": "Assigned queue token position upon arrival", "unit": "rank", "range": ">= 1"},
    "patients_waiting_ahead": {"type": "integer", "description": "Number of waiting patients ahead in line", "unit": "count", "range": ">= 0"},
    "is_doctor_active_consultation": {"type": "binary", "description": "1 if doctor is currently with a patient, else 0", "unit": "flag", "range": "{0, 1}"},
    "historical_avg_consultation_minutes": {"type": "float", "description": "Historical rolling baseline consultation duration", "unit": "minutes", "range": "[5, 60]"},
    "actual_wait_minutes": {"type": "float", "description": "TARGET: Elapsed minutes between check-in and doctor call", "unit": "minutes", "range": ">= 0.0"},
}

# ---------------------------------------------------------------------------
# No-Show Classification Schema
# ---------------------------------------------------------------------------
NOSHOW_TARGET = "is_no_show"

NOSHOW_FEATURES: List[str] = [
    "lead_time_days",
    "day_of_week",
    "slot_hour",
    "is_weekend",
    "doctor_specialty",
    "consultation_fee",
    "patient_prior_appointments",
    "patient_prior_no_shows",
    "patient_prior_no_show_rate",
    "has_notes",
]

NOSHOW_FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "lead_time_days": {"type": "integer", "description": "Days between booking creation date and appointment date", "unit": "days", "range": ">= 0"},
    "day_of_week": {"type": "integer", "description": "Day of appointment (0=Monday, 6=Sunday)", "unit": "day_index", "range": "[0, 6]"},
    "slot_hour": {"type": "integer", "description": "Scheduled appointment hour", "unit": "hour_24", "range": "[8, 18]"},
    "is_weekend": {"type": "binary", "description": "1 if appointment is on Saturday or Sunday, else 0", "unit": "flag", "range": "{0, 1}"},
    "doctor_specialty": {"type": "categorical", "description": "Doctor's clinical specialty", "unit": "category"},
    "consultation_fee": {"type": "float", "description": "Doctor consultation fee", "unit": "INR", "range": "[200, 5000]"},
    "patient_prior_appointments": {"type": "integer", "description": "Cumulative appointments booked prior to this date", "unit": "count", "range": ">= 0"},
    "patient_prior_no_shows": {"type": "integer", "description": "Cumulative unexcused absences prior to this date", "unit": "count", "range": ">= 0"},
    "patient_prior_no_show_rate": {"type": "float", "description": "Historical ratio of no-shows to prior appointments", "unit": "ratio", "range": "[0.0, 1.0]"},
    "has_notes": {"type": "binary", "description": "1 if patient added clinical notes during booking, else 0", "unit": "flag", "range": "{0, 1}"},
    "is_no_show": {"type": "binary", "description": "TARGET: 1 if appointment was a no-show, 0 if patient attended", "unit": "flag", "range": "{0, 1}"},
}

# Known supported clinical specialties
CLINICAL_SPECIALTIES = [
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Gastroenterology",
    "Oncology",
    "Pediatrics",
    "Nephrology",
    "Pulmonology",
    "Dermatology",
    "General Medicine",
]
