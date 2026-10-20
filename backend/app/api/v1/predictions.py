"""
ML Prediction API Endpoints for MediSmart.

Exposes the centralized in-memory ML prediction service for:
1. Patient Waiting-Time Regression (POST /api/v1/predictions/waiting-time)
2. Appointment No-Show Classification (POST /api/v1/predictions/no-show)
3. Model Service Readiness Status (GET /api/v1/predictions/status)

Security & Safety:
- Protected with standard active-user authentication (get_current_active_user).
- Pure in-memory inference without database mutations or table joins.
- Sanitized error responses without internal filesystem paths or stack traces.
- Explicit disclosure that all predictions derive from synthetic simulation models.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.ml import (
    NoShowPredictionRequest,
    NoShowPredictionResponse,
    WaitingTimePredictionRequest,
    WaitingTimePredictionResponse,
)
from app.services.ml_prediction import (
    ModelArtifactNotFoundError,
    ModelInferenceError,
    ml_prediction_service,
)

logger = logging.getLogger("medismart.api.predictions")

router = APIRouter()


@router.post(
    "/waiting-time",
    response_model=WaitingTimePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict patient waiting time at check-in",
    description=(
        "Estimates elapsed minutes until consultation call based on clinical department, "
        "queue depth, doctor pacing, and arrival timing. Trained on synthetic simulation data."
    ),
)
async def predict_waiting_time(
    data: WaitingTimePredictionRequest,
    current_user: User = Depends(get_current_active_user),
) -> WaitingTimePredictionResponse:
    """
    Computes expected wait time in minutes for a patient arrival event.
    Delegates to the shared ML prediction service.
    """
    try:
        return ml_prediction_service.predict_waiting_time(data)
    except ModelArtifactNotFoundError as e:
        logger.error("Waiting-time model unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Waiting-time prediction model is temporarily unavailable.",
        ) from None
    except ModelInferenceError as e:
        logger.exception("Waiting-time prediction inference failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Waiting-time prediction calculation failed.",
        ) from None
    except Exception as e:
        logger.exception("Unexpected error in waiting-time prediction endpoint.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction.",
        ) from None


@router.post(
    "/no-show",
    response_model=NoShowPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict appointment no-show probability and risk band",
    description=(
        "Estimates probability of unexcused patient absence based on scheduling lead time, "
        "historical attendance, slot hour, and department. Trained on synthetic data."
    ),
)
async def predict_no_show(
    data: NoShowPredictionRequest,
    current_user: User = Depends(get_current_active_user),
) -> NoShowPredictionResponse:
    """
    Computes no-show probability and illustrative risk band for an appointment booking.
    Delegates to the shared ML prediction service.
    """
    try:
        return ml_prediction_service.predict_no_show(data)
    except ModelArtifactNotFoundError as e:
        logger.error("No-show model unavailable: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Appointment no-show prediction model is temporarily unavailable.",
        ) from None
    except ModelInferenceError as e:
        logger.exception("No-show prediction inference failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Appointment no-show prediction calculation failed.",
        ) from None
    except Exception as e:
        logger.exception("Unexpected error in no-show prediction endpoint.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during prediction.",
        ) from None


@router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get ML prediction service and model status",
    description="Returns the initialization and availability status of all ML models.",
)
async def get_prediction_service_status(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Reports readiness and metadata for both ML models.
    """
    return ml_prediction_service.get_service_status()
