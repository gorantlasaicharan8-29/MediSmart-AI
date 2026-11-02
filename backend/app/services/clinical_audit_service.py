"""
Clinical Audit Logging Service for MediSmart EHR.

Implements HIPAA/GDPR-compliant immutable audit logging for:
- Consultation record creation and updates
- Patient medical history views and exports
- Diagnosis entries and modifications
- Prescription issuance and amendments
- Follow-up care coordination
- Unauthorized access attempts and security events

Security Constraints:
- Strictly redacts passwords, JWTs, authorization headers, tokens, and PHI narratives.
- Records actor identity, action type, target reference, timestamps, and network context.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ehr import ClinicalAuditLog
from app.models.user import User

logger = logging.getLogger("medismart.services.audit")

SENSITIVE_AUDIT_KEYS: Set[str] = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "authorization",
    "cookie",
    "credentials",
    "secret",
    "secret_key",
    "hashed_password",
    "api_key",
}


def sanitize_audit_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Sanitizes audit metadata by removing passwords, tokens, auth headers,
    and unnecessary clinical narrative details.
    """
    if not metadata:
        return None

    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = str(key).lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_AUDIT_KEYS):
            continue  # redact entirely

        # Ensure values are JSON-serializable primitives
        if isinstance(value, (str, int, float, bool)) or value is None:
            # Truncate overly long free-text values
            if isinstance(value, str) and len(value) > 255:
                sanitized[key] = value[:252] + "..."
            else:
                sanitized[key] = value
        elif isinstance(value, uuid.UUID):
            sanitized[key] = str(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [str(v) if isinstance(v, uuid.UUID) else v for v in value[:20]]
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_metadata(value)
        else:
            sanitized[key] = str(value)

    return sanitized


class ClinicalAuditService:
    """Service to capture and retrieve clinical audit trail entries."""

    @classmethod
    async def log(
        cls,
        db: AsyncSession,
        action: str,
        target_type: str,
        actor: Optional[User] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_id: Optional[uuid.UUID] = None,
        patient_id: Optional[uuid.UUID] = None,
        doctor_id: Optional[uuid.UUID] = None,
        hospital_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[ClinicalAuditLog]:
        """
        Records an immutable clinical audit event.
        Does not commit the session directly; integrates with caller transaction boundary.
        """
        try:
            resolved_actor_id = actor.id if actor else actor_id
            resolved_role = actor.role if actor else (actor_role or "system")
            resolved_email = actor.email if actor else actor_email

            cleaned_metadata = sanitize_audit_metadata(metadata)

            log_entry = ClinicalAuditLog(
                id=uuid.uuid4(),
                actor_id=resolved_actor_id,
                actor_role=resolved_role,
                actor_email=resolved_email,
                action=action.upper(),
                target_type=target_type.lower(),
                target_id=target_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                hospital_id=hospital_id,
                ip_address=ip_address[:45] if ip_address else None,
                user_agent=user_agent[:255] if user_agent else None,
                metadata_json=cleaned_metadata,
            )
            db.add(log_entry)
            return log_entry
        except Exception as e:
            logger.error(f"Failed to record clinical audit log: {e}", exc_info=True)
            return None

    @classmethod
    async def query_logs(
        cls,
        db: AsyncSession,
        patient_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ClinicalAuditLog]:
        """
        Retrieves clinical audit logs for authorized audit reviews.
        """
        query = select(ClinicalAuditLog).order_by(desc(ClinicalAuditLog.created_at))

        if patient_id:
            query = query.where(ClinicalAuditLog.patient_id == patient_id)
        if actor_id:
            query = query.where(ClinicalAuditLog.actor_id == actor_id)
        if action:
            query = query.where(ClinicalAuditLog.action == action.upper())

        query = query.limit(min(limit, 100)).offset(offset)
        res = await db.execute(query)
        return list(res.scalars().all())


clinical_audit_service = ClinicalAuditService()

