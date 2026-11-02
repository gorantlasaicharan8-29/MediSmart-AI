import uuid
from datetime import date
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.doctor import DoctorResponse


class DoctorRecommendationRequest(BaseModel):
    """Input preferences for AI-powered doctor recommendation."""
    specialty: Optional[str] = Field(None, description="Preferred medical specialty (e.g., Cardiology, Neurology)")
    city: Optional[str] = Field(None, description="Preferred city or location")
    hospital_id: Optional[uuid.UUID] = Field(None, description="Preferred hospital ID")
    hospital_name: Optional[str] = Field(None, description="Preferred hospital name keyword")
    max_fee: Optional[float] = Field(None, ge=0.0, description="Maximum consultation fee budget (INR)")
    preferred_date: Optional[date] = Field(None, description="Preferred consultation date (YYYY-MM-DD)")
    consultation_type: Optional[str] = Field("OPD / In-Person", description="Consultation type e.g. 'OPD / In-Person' or 'Teleconsultation'")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of recommendations to return")


class DoctorRecommendationItem(BaseModel):
    """An individual doctor recommendation with transparent score and explainability."""
    doctor: DoctorResponse
    match_score: int = Field(..., ge=0, le=100, description="Overall match score (0-100)")
    match_percentage: int = Field(..., ge=0, le=100, description="Match percentage indicator")
    explanations: List[str] = Field(default_factory=list, description="Data-backed reasons why this doctor was recommended")
    next_available_slot: Optional[str] = Field(None, description="Earliest confirmed open slot on preferred date (HH:MM)")
    next_available_date: Optional[date] = Field(None, description="Date for which slot was evaluated")
    is_slot_available: bool = Field(False, description="Whether at least one slot is open on the requested date")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, description="Transparent score breakdown by criteria")

    model_config = ConfigDict(from_attributes=True)


class DoctorRecommendationResponse(BaseModel):
    """Response containing ranked doctor recommendations and metadata."""
    items: List[DoctorRecommendationItem]
    total_evaluated: int
    preferred_date: date
    preferences_applied: DoctorRecommendationRequest
