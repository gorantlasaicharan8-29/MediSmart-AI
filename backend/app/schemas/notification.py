import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.notification import SENSITIVE_METADATA_KEYS, sanitize_metadata

# Additional clinical and credential keys to redact defensively from response payloads
DEFENSIVE_REDACT_KEYS: Set[str] = {
    *SENSITIVE_METADATA_KEYS,
    "doctor_notes",
    "patient_notes",
    "medical_notes",
    "diagnosis",
    "prescription",
    "credentials",
    "api_key",
}


def sanitize_response_metadata(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Sanitizes metadata dictionary removing any sensitive clinical or auth keys."""
    if not data:
        return None

    sanitized = {}
    for k, v in data.items():
        k_lower = k.lower()
        if k_lower in DEFENSIVE_REDACT_KEYS or any(s in k_lower for s in ("token", "password", "secret", "note")):
            continue
        if isinstance(v, uuid.UUID):
            sanitized[k] = str(v)
        elif isinstance(v, datetime):
            sanitized[k] = v.isoformat()
        elif isinstance(v, dict):
            sanitized[k] = sanitize_response_metadata(v)
        else:
            sanitized[k] = v

    return sanitized


class NotificationResponse(BaseModel):
    """Safe public representation of a user notification."""
    id: uuid.UUID
    category: str
    event_type: str
    title: str
    message: str
    urgency: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("metadata_json", mode="before")
    @classmethod
    def strip_sensitive_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return sanitize_response_metadata(v)
        return v


class NotificationListResponse(BaseModel):
    """Paginated notification response payload."""
    items: List[NotificationResponse]
    total: int = Field(..., ge=0, description="Total matching notifications count")
    limit: int = Field(..., ge=1, description="Pagination limit")
    offset: int = Field(..., ge=0, description="Pagination offset")
    unread_count: int = Field(..., ge=0, description="Total unread notifications for the user")


class NotificationReadAllResponse(BaseModel):
    """Response payload for marking all notifications as read."""
    updated_count: int = Field(..., ge=0, description="Count of notifications marked as read")
    message: str = Field(
        default="All notifications marked as read.",
        description="Informational status message",
    )

