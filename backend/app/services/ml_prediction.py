"""
MediSmart ML Prediction Service bridge.

Exposes the centralized MLPredictionService from app.ml.service.
"""
from app.ml.service import (
    MLPredictionService,
    MLServiceError,
    ModelArtifactNotFoundError,
    ModelInferenceError,
    ModelNotLoadedError,
    ml_prediction_service,
)

__all__ = [
    "MLPredictionService",
    "MLServiceError",
    "ModelArtifactNotFoundError",
    "ModelInferenceError",
    "ModelNotLoadedError",
    "ml_prediction_service",
]
