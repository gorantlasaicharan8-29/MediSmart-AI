import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


class HospitalBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=3)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    specialties: List[str] = Field(default_factory=list)
    facilities: List[str] = Field(default_factory=list)
    is_active: bool = True
    data_source: str = Field("verified", max_length=50)
    source_attribution: Optional[str] = Field(None, max_length=255)


class HospitalCreate(HospitalBase):
    """Schema for creating a new hospital."""
    pass


class HospitalUpdate(BaseModel):
    """Schema for updating an existing hospital. All fields optional."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    address: Optional[str] = Field(None, min_length=3)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    specialties: Optional[List[str]] = None
    facilities: Optional[List[str]] = None
    is_active: Optional[bool] = None
    data_source: Optional[str] = Field(None, max_length=50)
    source_attribution: Optional[str] = Field(None, max_length=255)


class HospitalResponse(HospitalBase):
    """Public hospital representation."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    @computed_field
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    model_config = ConfigDict(from_attributes=True)


class HospitalListResponse(BaseModel):
    """Paginated list of hospital records."""
    items: List[HospitalResponse]
    total: int
    limit: int
    offset: int
