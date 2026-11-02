import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.recommendation import (
    DoctorRecommendationRequest,
    DoctorRecommendationResponse,
)
from app.services.recommendation import DoctorRecommendationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/doctors",
    response_model=DoctorRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI-powered doctor recommendations",
    description=(
        "Calculates explainable, data-driven doctor recommendations ranked by clinical specialization, "
        "location, hospital affiliation, consultation fee budget, and confirmed slot availability."
    ),
)
async def get_doctor_recommendations(
    preferences: DoctorRecommendationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Evaluates active doctors against patient healthcare preferences using a transparent,
    explainable weighted scoring algorithm.
    """
    logger.info(
        "User %s requested doctor recommendations (specialty=%s, city=%s, budget=%s, date=%s)",
        current_user.id,
        preferences.specialty,
        preferences.city,
        preferences.max_fee,
        preferences.preferred_date,
    )
    return await DoctorRecommendationService.get_recommendations(preferences, db)

