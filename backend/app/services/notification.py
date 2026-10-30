import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import user_ws_manager
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.queue import QueueEntry

logger = logging.getLogger(__name__)

# Valid categorization and priority vocabularies
ALLOWED_CATEGORIES: Set[str] = {"appointment", "queue", "system"}
ALLOWED_URGENCIES: Set[str] = {"low", "normal", "high", "urgent"}

# Sensitive fields to redact from notification metadata
SENSITIVE_METADATA_KEYS: Set[str] = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "credit_card",
    "clinical_notes",
    "notes",
    "cancellation_reason",  # full free-form notes redacted from JSON payload; short reason in body
}


@dataclass
class NotificationResult:
    """Result container for notification creation attempts."""
    notification: Optional[Notification]
    is_duplicate: bool = False
    created: bool = False


def sanitize_metadata(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Sanitizes arbitrary dictionary payloads for storage in metadata_json.
    - Strips authentication tokens, passwords, and sensitive keys.
    - Converts non-JSON serializable primitives (UUID, datetime, date, time) to ISO strings.
    """
    if not data:
        return None

    sanitized = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_METADATA_KEYS:
            continue
        if isinstance(v, uuid.UUID):
            sanitized[k] = str(v)
        elif isinstance(v, (datetime, date, time)):
            sanitized[k] = v.isoformat()
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
        else:
            sanitized[k] = v

    return sanitized


class NotificationService:
    """
    Centralized service for creating and persisting user notifications.
    - Validates category, event type, urgency, title, and body text.
    - Uses nested savepoints (`begin_nested()`) to guarantee idempotency without
      breaking parent database transaction state.
    - Fully decoupled from external messaging networks (SMS/Email/WebSockets).
    """

    async def create_notification(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        message: str,
        category: str = "appointment",
        event_type: str = "general",
        urgency: str = "normal",
        idempotency_key: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """
        Creates and stores a notification record.
        - If an idempotency collision occurs, gracefully returns `is_duplicate=True`
          and the existing notification without rolling back the caller's transaction.
        - Respects caller transaction boundaries by default (`auto_commit=False`).
        """
        # 1. Validation
        if not isinstance(user_id, uuid.UUID):
            try:
                user_id = uuid.UUID(str(user_id))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid user_id provided: {user_id}") from exc

        if not title or not title.strip():
            raise ValueError("Notification title cannot be empty.")
        if len(title) > 255:
            raise ValueError("Notification title exceeds maximum length of 255 characters.")

        if not message or not message.strip():
            raise ValueError("Notification message cannot be empty.")

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"Invalid notification category '{category}'. Allowed: {ALLOWED_CATEGORIES}"
            )

        if urgency not in ALLOWED_URGENCIES:
            raise ValueError(
                f"Invalid notification urgency '{urgency}'. Allowed: {ALLOWED_URGENCIES}"
            )

        if not event_type or not event_type.strip():
            raise ValueError("Notification event_type cannot be empty.")
        if len(event_type) > 50:
            raise ValueError("Notification event_type exceeds maximum length of 50 characters.")

        clean_idemp_key = idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
        if clean_idemp_key and len(clean_idemp_key) > 100:
            raise ValueError("Notification idempotency_key exceeds maximum length of 100 characters.")

        sanitized_meta = sanitize_metadata(metadata_json)

        # 2. Model Instantiation
        notification = Notification(
            user_id=user_id,
            category=category,
            event_type=event_type.strip(),
            title=title.strip(),
            message=message.strip(),
            urgency=urgency,
            idempotency_key=clean_idemp_key,
            metadata_json=sanitized_meta,
            is_read=False,
            read_at=None,
        )

        # 3. Transactional Insertion via Nested Savepoint
        # A nested savepoint protects the outer database transaction if an idempotency collision trips.
        try:
            async with db.begin_nested():
                db.add(notification)
                await db.flush()
        except IntegrityError as exc:
            orig_str = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if "uq_user_notification_idempotency" in orig_str:
                logger.info(
                    f"Duplicate notification suppressed by idempotency_key '{clean_idemp_key}' for user {user_id}"
                )
                # Fetch and return existing notification
                stmt = select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.idempotency_key == clean_idemp_key,
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()
                return NotificationResult(
                    notification=existing,
                    is_duplicate=True,
                    created=False,
                )
            # Re-raise any other integrity conflicts (e.g. invalid foreign key user_id)
            raise
        except ProgrammingError as exc:
            orig_str = str(exc.orig) if hasattr(exc, "orig") else str(exc)
            if 'relation "notifications" does not exist' in orig_str or "UndefinedTableError" in orig_str:
                logger.warning(
                    "Notifications table does not exist in the database. Notification persistence skipped until migration 'a7c8e91f0d32' is applied."
                )
                return NotificationResult(
                    notification=None,
                    is_duplicate=False,
                    created=False,
                )
            raise

        # Stage real-time WebSocket push event to be delivered strictly after commit
        self._stage_post_commit_dispatch(db, notification)

        if auto_commit:
            await db.commit()
            await db.refresh(notification)

        return NotificationResult(
            notification=notification,
            is_duplicate=False,
            created=True,
        )

    @staticmethod
    def _stage_post_commit_dispatch(db: AsyncSession, notification: Notification) -> None:
        """
        Stages a real-time WebSocket push event on the database session.
        Guaranteed to be dispatched ONLY after the surrounding database transaction
        commits successfully. If the transaction rolls back, all staged events are discarded.
        """
        if not hasattr(db, "sync_session"):
            return

        sync_session = db.sync_session
        staged = sync_session.info.setdefault("_staged_notification_events", [])

        # Build minimal, zero-PII event envelope
        created_iso = (
            notification.created_at.isoformat()
            if getattr(notification, "created_at", None)
            else datetime.now(timezone.utc).isoformat()
        )
        payload = {
            "event": "NOTIFICATION_CREATED",
            "notification": {
                "id": str(notification.id),
                "category": notification.category,
                "event_type": notification.event_type,
                "title": notification.title,
                "urgency": notification.urgency,
                "is_read": bool(notification.is_read),
                "created_at": created_iso,
            },
        }
        staged.append((str(notification.user_id), payload))

        # Register session event listeners once per transaction/session
        if not sync_session.info.get("_notification_listeners_registered"):
            sync_session.info["_notification_listeners_registered"] = True

            def after_commit(s):
                # Ignore inner savepoint commits; only dispatch when outer transaction commits
                if s.in_nested_transaction():
                    return
                events = s.info.pop("_staged_notification_events", [])
                if not events:
                    return
                try:
                    loop = asyncio.get_running_loop()
                    for uid, msg in events:
                        loop.create_task(user_ws_manager.broadcast_to_user(uid, msg))
                except RuntimeError:
                    # Event loop closed or not running
                    pass

            def after_rollback(s):
                # Ignore inner savepoint rollbacks; preserve outer staged events
                if s.in_nested_transaction():
                    return
                s.info.pop("_staged_notification_events", None)

            event.listen(sync_session, "after_commit", after_commit)
            event.listen(sync_session, "after_rollback", after_rollback)

    # -------------------------------------------------------------------------
    # Domain Event Integration Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _safe_get_doctor_name(entity: Any, fallback: str = "your specialist") -> str:
        """Extracts doctor name if already eagerly loaded, without triggering DetachedInstanceError."""
        if hasattr(entity, "__dict__") and "doctor" in entity.__dict__:
            doc = entity.__dict__["doctor"]
            if doc and hasattr(doc, "__dict__") and "user" in doc.__dict__:
                u = doc.__dict__["user"]
                if u and hasattr(u, "full_name") and u.full_name:
                    return u.full_name
        return fallback

    @staticmethod
    def _safe_get_hospital_name(entity: Any, fallback: str = "the clinic") -> str:
        """Extracts hospital name if already eagerly loaded, without triggering DetachedInstanceError."""
        if hasattr(entity, "__dict__") and "hospital" in entity.__dict__:
            hosp = entity.__dict__["hospital"]
            if hosp and hasattr(hosp, "name") and hosp.name:
                return hosp.name
        return fallback

    async def create_appointment_booked_notification(
        self,
        db: AsyncSession,
        appointment: Appointment,
        doctor_name: Optional[str] = None,
        hospital_name: Optional[str] = None,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates patient notification upon successful appointment booking."""
        doc_name = doctor_name or self._safe_get_doctor_name(appointment)
        hosp_name = hospital_name or self._safe_get_hospital_name(appointment)
        date_str = appointment.appointment_date.strftime("%b %d, %Y")
        time_str = appointment.appointment_time.strftime("%I:%M %p")

        title = "Appointment Confirmed"
        message = (
            f"Your appointment with Dr. {doc_name} at {hosp_name} is scheduled for "
            f"{date_str} at {time_str}. Token reference: {appointment.appointment_token}."
        )

        idempotency_key = f"appt_booked:{appointment.id}"
        metadata = {
            "appointment_id": str(appointment.id),
            "doctor_id": str(appointment.doctor_id),
            "hospital_id": str(appointment.hospital_id),
            "appointment_token": appointment.appointment_token,
            "appointment_date": appointment.appointment_date.isoformat(),
            "appointment_time": appointment.appointment_time.isoformat(),
        }

        return await self.create_notification(
            db=db,
            user_id=appointment.patient_id,
            category="appointment",
            event_type="appointment_booked",
            title=title,
            message=message,
            urgency="normal",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )

    async def create_appointment_cancelled_notification(
        self,
        db: AsyncSession,
        appointment: Appointment,
        reason: Optional[str] = None,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates patient notification upon appointment cancellation."""
        date_str = appointment.appointment_date.strftime("%b %d, %Y")
        time_str = appointment.appointment_time.strftime("%I:%M %p")

        title = "Appointment Cancelled"
        message = f"Your appointment scheduled for {date_str} at {time_str} has been cancelled."
        if reason:
            message += f" Note: {reason.strip()}."

        idempotency_key = f"appt_cancelled:{appointment.id}"
        metadata = {
            "appointment_id": str(appointment.id),
            "doctor_id": str(appointment.doctor_id),
            "appointment_token": appointment.appointment_token,
        }

        return await self.create_notification(
            db=db,
            user_id=appointment.patient_id,
            category="appointment",
            event_type="appointment_cancelled",
            title=title,
            message=message,
            urgency="high",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )

    async def create_queue_checked_in_notification(
        self,
        db: AsyncSession,
        queue_entry: QueueEntry,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates patient notification upon clinic arrival and queue check-in."""
        token_disp = queue_entry.token_display
        pos = queue_entry.position

        title = "Checked In to Queue"
        message = f"You have checked in successfully. Your queue token is {token_disp} (Position #{pos})."

        idempotency_key = f"queue_checkin:{queue_entry.id}"
        metadata = {
            "queue_entry_id": str(queue_entry.id),
            "appointment_id": str(queue_entry.appointment_id),
            "doctor_id": str(queue_entry.doctor_id),
            "token_display": token_disp,
            "token_number": queue_entry.token_number,
            "position": pos,
        }

        return await self.create_notification(
            db=db,
            user_id=queue_entry.patient_id,
            category="queue",
            event_type="queue_checked_in",
            title=title,
            message=message,
            urgency="normal",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )

    async def create_queue_called_notification(
        self,
        db: AsyncSession,
        queue_entry: QueueEntry,
        doctor_name: Optional[str] = None,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates urgent notification when patient is called into consultation."""
        token_disp = queue_entry.token_display
        doc_name = doctor_name or self._safe_get_doctor_name(queue_entry, fallback="the doctor")

        title = "Your Turn — Please Proceed"
        message = f"Token {token_disp} has been called! Please proceed to Dr. {doc_name}'s consultation room."

        # Keyed to timestamp to prevent repeat notifications for same call
        called_str = queue_entry.called_at.isoformat() if queue_entry.called_at else "called"
        idempotency_key = f"queue_called:{queue_entry.id}:{called_str}"
        metadata = {
            "queue_entry_id": str(queue_entry.id),
            "doctor_id": str(queue_entry.doctor_id),
            "token_display": token_disp,
            "token_number": queue_entry.token_number,
        }

        return await self.create_notification(
            db=db,
            user_id=queue_entry.patient_id,
            category="queue",
            event_type="queue_patient_called",
            title=title,
            message=message,
            urgency="urgent",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )

    async def create_queue_completed_notification(
        self,
        db: AsyncSession,
        queue_entry: QueueEntry,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates notification when clinical consultation concludes."""
        token_disp = queue_entry.token_display

        title = "Consultation Completed"
        message = f"Your consultation for token {token_disp} has been marked complete. Thank you."

        idempotency_key = f"queue_completed:{queue_entry.id}"
        metadata = {
            "queue_entry_id": str(queue_entry.id),
            "token_display": token_disp,
        }

        return await self.create_notification(
            db=db,
            user_id=queue_entry.patient_id,
            category="queue",
            event_type="queue_completed",
            title=title,
            message=message,
            urgency="low",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )

    async def create_queue_skipped_notification(
        self,
        db: AsyncSession,
        queue_entry: QueueEntry,
        auto_commit: bool = False,
    ) -> NotificationResult:
        """Generates notification when patient was called but absent."""
        token_disp = queue_entry.token_display

        title = "Queue Call Missed"
        message = (
            f"Your token {token_disp} was called but marked absent. "
            "Please check in with the reception or clinic desk to be re-queued."
        )

        idempotency_key = f"queue_skipped:{queue_entry.id}"
        metadata = {
            "queue_entry_id": str(queue_entry.id),
            "token_display": token_disp,
        }

        return await self.create_notification(
            db=db,
            user_id=queue_entry.patient_id,
            category="queue",
            event_type="queue_skipped",
            title=title,
            message=message,
            urgency="high",
            idempotency_key=idempotency_key,
            metadata_json=metadata,
            auto_commit=auto_commit,
        )


notification_service = NotificationService()
