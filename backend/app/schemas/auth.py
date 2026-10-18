import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Schema for public user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    role: str = Field("patient", description="Role: 'patient' or 'doctor'")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserLoginRequest(BaseModel):
    """Schema for user credentials login."""
    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    """Safe public user representation without sensitive fields."""
    id: uuid.UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Access token payload returned upon successful authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse
