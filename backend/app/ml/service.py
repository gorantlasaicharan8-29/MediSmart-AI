"""
Shared ML Prediction Service for MediSmart.

Provides safe, in-memory inference for:
1. Patient Waiting-Time Regression (minutes until consultation call)
2. Appointment No-Show Classification (unexcused absence probability & thresholding)

Design Principles:
- Lazy / startup loading with in-memory caching (zero per-request disk I/O).
- Strict Pydantic input validation for feature types, bounds, and finite values.
- Non-negative guarantee on wait times (>= 0.0 min).
- Bounded probabilities on no-show ([0.0, 1.0]).
- Explicit synthetic training provenance disclosure on all outputs.
- Read-only execution with zero database dependencies or mutations.
- Sanitized exception handling without leaking internal filesystem paths.
"""
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from app.ml.config import (
    NOSHOW_MODEL_PATH,
    WAITING_TIME_MODEL_PATH,
)
from app.ml.estimators import NonNegativeRegressor, ThresholdClassifier
from app.schemas.ml import (
    NoShowPredictionRequest,
    NoShowPredictionResponse,
    WaitingTimePredictionRequest,
    WaitingTimePredictionResponse,
)

logger = logging.getLogger("medismart.ml.service")

# Default metadata fallback paths
WAITING_TIME_METRICS_PATH = WAITING_TIME_MODEL_PATH.parent / "waiting_time_metrics.json"
NOSHOW_METRICS_PATH = NOSHOW_MODEL_PATH.parent / "noshow_metrics.json"

# Strict feature order matching training pipelines
WAITING_TIME_FEATURE_ORDER = [
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

NOSHOW_FEATURE_ORDER = [
    "doctor_specialty",
    "lead_time_days",
    "day_of_week",
    "slot_hour",
    "is_weekend",
    "consultation_fee",
    "patient_prior_appointments",
    "patient_prior_no_shows",
    "patient_prior_no_show_rate",
    "has_notes",
]


class MLServiceError(Exception):
    """Base exception for MediSmart ML prediction service."""


class ModelArtifactNotFoundError(MLServiceError):
    """Raised when a required model artifact is missing from disk."""


class ModelNotLoadedError(MLServiceError):
    """Raised when prediction is requested on an uninitialized model pipeline."""


class ModelInferenceError(MLServiceError):
    """Raised when feature transformation or model inference fails."""


class MLPredictionService:
    """
    Singleton-capable prediction service managing lifecycle, caching,
    and inference execution for all MediSmart machine learning models.
    """

    def __init__(
        self,
        waiting_time_model_path: Path = WAITING_TIME_MODEL_PATH,
        waiting_time_metrics_path: Path = WAITING_TIME_METRICS_PATH,
        noshow_model_path: Path = NOSHOW_MODEL_PATH,
        noshow_metrics_path: Path = NOSHOW_METRICS_PATH,
    ):
        self._waiting_time_model_path = waiting_time_model_path
        self._waiting_time_metrics_path = waiting_time_metrics_path
        self._noshow_model_path = noshow_model_path
        self._noshow_metrics_path = noshow_metrics_path

        self._waiting_time_pipeline: Optional[Pipeline] = None
        self._waiting_time_metadata: Optional[Dict[str, Any]] = None

        self._noshow_pipeline: Optional[Pipeline] = None
        self._noshow_metadata: Optional[Dict[str, Any]] = None

        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Model Lifecycle & Artifact Loading
    # -----------------------------------------------------------------------

    def load_waiting_time_model(self, force_reload: bool = False) -> Pipeline:
        """
        Loads and caches the waiting-time regression pipeline in memory.
        Thread-safe; avoids reloading if already present unless force_reload=True.
        """
        if self._waiting_time_pipeline is not None and not force_reload:
            return self._waiting_time_pipeline

        with self._lock:
            if self._waiting_time_pipeline is not None and not force_reload:
                return self._waiting_time_pipeline

            if not self._waiting_time_model_path.exists():
                logger.error("Waiting-time model artifact missing: %s", self._waiting_time_model_path.name)
                raise ModelArtifactNotFoundError(
                    "Waiting-time prediction model artifact is unavailable. "
                    "Ensure Phase 6.2 training has completed successfully."
                )

            try:
                pipeline = joblib.load(self._waiting_time_model_path)
                self._waiting_time_pipeline = pipeline
                logger.info("Successfully loaded waiting-time pipeline into memory.")
            except Exception as e:
                logger.exception("Failed to deserialize waiting-time model artifact.")
                raise ModelInferenceError("Failed to initialize waiting-time prediction model.") from e

            # Optional metadata load
            if self._waiting_time_metrics_path.exists():
                try:
                    with open(self._waiting_time_metrics_path, "r", encoding="utf-8") as f:
                        self._waiting_time_metadata = json.load(f)
                except Exception:
                    logger.warning("Could not read waiting-time metrics metadata JSON.")

            return self._waiting_time_pipeline

    def load_noshow_model(self, force_reload: bool = False) -> Pipeline:
        """
        Loads and caches the no-show classification pipeline in memory.
        Thread-safe; avoids reloading if already present unless force_reload=True.
        """
        if self._noshow_pipeline is not None and not force_reload:
            return self._noshow_pipeline

        with self._lock:
            if self._noshow_pipeline is not None and not force_reload:
                return self._noshow_pipeline

            if not self._noshow_model_path.exists():
                logger.error("No-show model artifact missing: %s", self._noshow_model_path.name)
                raise ModelArtifactNotFoundError(
                    "Appointment no-show prediction model artifact is unavailable. "
                    "Ensure Phase 6.3 training has completed successfully."
                )

            try:
                pipeline = joblib.load(self._noshow_model_path)
                self._noshow_pipeline = pipeline
                logger.info("Successfully loaded no-show pipeline into memory.")
            except Exception as e:
                logger.exception("Failed to deserialize no-show model artifact.")
                raise ModelInferenceError("Failed to initialize no-show prediction model.") from e

            # Optional metadata load
            if self._noshow_metrics_path.exists():
                try:
                    with open(self._noshow_metrics_path, "r", encoding="utf-8") as f:
                        self._noshow_metadata = json.load(f)
                except Exception:
                    logger.warning("Could not read no-show metrics metadata JSON.")

            return self._noshow_pipeline

    def load_all_models(self, force_reload: bool = False) -> None:
        """Eagerly loads both model pipelines during application startup."""
        self.load_waiting_time_model(force_reload=force_reload)
        self.load_noshow_model(force_reload=force_reload)

    def get_service_status(self) -> Dict[str, Any]:
        """Returns the initialization status and metadata for all prediction models."""
        return {
            "waiting_time_model": {
                "loaded": self._waiting_time_pipeline is not None,
                "artifact_exists": self._waiting_time_model_path.exists(),
                "model_name": (
                    self._waiting_time_metadata.get("selected_model", "xgboost")
                    if self._waiting_time_metadata
                    else "xgboost"
                ),
                "is_synthetic": True,
            },
            "noshow_model": {
                "loaded": self._noshow_pipeline is not None,
                "artifact_exists": self._noshow_model_path.exists(),
                "model_name": (
                    self._noshow_metadata.get("selected_model", "logistic_regression")
                    if self._noshow_metadata
                    else "logistic_regression"
                ),
                "is_synthetic": True,
            },
        }

    # -----------------------------------------------------------------------
    # Inference: Waiting-Time Prediction
    # -----------------------------------------------------------------------

    def predict_waiting_time(
        self,
        request: WaitingTimePredictionRequest,
    ) -> WaitingTimePredictionResponse:
        """
        Computes predicted waiting time in minutes for a patient check-in event.
        Guarantees non-negative, finite output and returns provenance disclosures.
        """
        pipeline = self.load_waiting_time_model()

        # Build single-record DataFrame with exact training column order
        record = {
            "doctor_specialty": request.doctor_specialty,
            "doctor_experience_years": request.doctor_experience_years,
            "day_of_week": request.day_of_week,
            "slot_hour": request.slot_hour,
            "slot_minute": request.slot_minute,
            "arrival_lead_minutes": request.arrival_lead_minutes,
            "queue_position_at_checkin": request.queue_position_at_checkin,
            "patients_waiting_ahead": request.patients_waiting_ahead,
            "is_doctor_active_consultation": request.is_doctor_active_consultation,
            "historical_avg_consultation_minutes": request.historical_avg_consultation_minutes,
        }
        features_df = pd.DataFrame([record], columns=WAITING_TIME_FEATURE_ORDER)

        try:
            raw_pred = pipeline.predict(features_df)
            wait_minutes = float(raw_pred[0])
        except Exception as e:
            logger.exception("Waiting-time prediction failed during model evaluation.")
            raise ModelInferenceError("Failed to calculate waiting-time prediction.") from e

        # Ensure finite and non-negative
        if not np.isfinite(wait_minutes):
            logger.error("Non-finite prediction returned by waiting-time model: %s", wait_minutes)
            raise ModelInferenceError("Invalid non-finite waiting-time prediction generated.")

        bounded_wait = round(float(max(0.0, wait_minutes)), 1)
        model_name = (
            self._waiting_time_metadata.get("selected_model", "xgboost")
            if self._waiting_time_metadata
            else "xgboost"
        )

        return WaitingTimePredictionResponse(
            predicted_wait_minutes=bounded_wait,
            unit="minutes",
            model_name=model_name,
            model_version="1.0.0",
            prediction_source="ml_synthetic_model",
            is_synthetic_model=True,
            synthetic_notice=(
                "Trained exclusively on synthetic queue simulation data. "
                "Must not be represented as clinically calibrated observations."
            ),
        )

    # -----------------------------------------------------------------------
    # Inference: Appointment No-Show Prediction
    # -----------------------------------------------------------------------

    def predict_no_show(
        self,
        request: NoShowPredictionRequest,
    ) -> NoShowPredictionResponse:
        """
        Computes no-show probability and discrete classification for a scheduled appointment.
        Categorizes probability into an illustrative, non-diagnostic risk band.
        """
        pipeline = self.load_noshow_model()

        record = {
            "doctor_specialty": request.doctor_specialty,
            "lead_time_days": request.lead_time_days,
            "day_of_week": request.day_of_week,
            "slot_hour": request.slot_hour,
            "is_weekend": request.is_weekend,
            "consultation_fee": request.consultation_fee,
            "patient_prior_appointments": request.patient_prior_appointments,
            "patient_prior_no_shows": request.patient_prior_no_shows,
            "patient_prior_no_show_rate": request.patient_prior_no_show_rate,
            "has_notes": request.has_notes,
        }
        features_df = pd.DataFrame([record], columns=NOSHOW_FEATURE_ORDER)

        try:
            probs = pipeline.predict_proba(features_df)
            preds = pipeline.predict(features_df)

            no_show_prob = float(probs[0, 1])
            predicted_binary = int(preds[0])
        except Exception as e:
            logger.exception("No-show prediction failed during model evaluation.")
            raise ModelInferenceError("Failed to calculate appointment no-show prediction.") from e

        # Ensure probability is finite and bounded in [0.0, 1.0]
        if not np.isfinite(no_show_prob):
            logger.error("Non-finite probability returned by no-show model: %s", no_show_prob)
            raise ModelInferenceError("Invalid non-finite no-show probability generated.")

        bounded_prob = round(float(np.clip(no_show_prob, 0.0, 1.0)), 4)

        # Illustrative risk band mapping (purely for demonstration; not diagnostic)
        if bounded_prob < 0.20:
            risk_band = "low"
        elif bounded_prob < 0.40:
            risk_band = "moderate"
        else:
            risk_band = "high"

        # Read threshold from metadata or classifier wrapper
        threshold = 0.50
        if self._noshow_metadata and "calibrated_threshold" in self._noshow_metadata:
            threshold = float(self._noshow_metadata["calibrated_threshold"])
        elif hasattr(pipeline.named_steps.get("clf"), "threshold"):
            threshold = float(pipeline.named_steps["clf"].threshold)

        model_name = (
            self._noshow_metadata.get("selected_model", "logistic_regression")
            if self._noshow_metadata
            else "logistic_regression"
        )

        return NoShowPredictionResponse(
            no_show_probability=bounded_prob,
            predicted_no_show=predicted_binary,
            decision_threshold=threshold,
            risk_band=risk_band,
            risk_band_notice="Illustrative risk band for demonstration purposes only. Not clinically validated.",
            model_name=model_name,
            model_version="1.0.0",
            prediction_source="ml_synthetic_model",
            is_synthetic_model=True,
            synthetic_notice=(
                "Trained exclusively on synthetic appointment data. "
                "Probabilities reflect synthetic behavior and must not be interpreted as validated clinical risk."
            ),
        )


# Global service instance
ml_prediction_service = MLPredictionService()
