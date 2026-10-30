import uuid
from datetime import date, datetime, time, timezone
import pytest
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import Appointment, Doctor, Hospital, Notification, QueueEntry, User
from app.services.notification import (
    NotificationResult,
    NotificationService,
    notification_service,
    sanitize_metadata,
)


@pytest.fixture
async def test_user():
    """Creates a temporary test user."""
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"notif_svc_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Notification Service Test User",
            role="patient",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    yield user

    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


@pytest.fixture
async def test_appointment_and_queue(test_user):
    """Sets up a complete test hospital, doctor, appointment, and queue entry."""
    async with AsyncSessionLocal() as session:
        # 1. Doctor user
        doc_user = User(
            email=f"doc_svc_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Dr. Test Specialist",
            role="doctor",
        )
        session.add(doc_user)
        await session.flush()

        # 2. Hospital
        hospital = Hospital(
            name=f"Metro General {uuid.uuid4().hex[:6]}",
            address="123 Health Ave",
            city="Metropolis",
            state="MetroState",
            phone="+1234567890",
            email=f"hosp_{uuid.uuid4().hex[:8]}@example.com",
            specialties=["Cardiology"],
            facilities=["ICU", "Lab"],
        )
        session.add(hospital)
        await session.flush()

        # 3. Doctor profile
        doctor = Doctor(
            user_id=doc_user.id,
            hospital_id=hospital.id,
            specialty="Cardiology",
            qualification="MD",
            experience_years=10,
            consultation_fee=100.0,
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            is_available=True,
        )
        session.add(doctor)
        await session.flush()

        # 4. Appointment
        appt_token = f"TEST-{uuid.uuid4().hex[:6].upper()}"
        appt = Appointment(
            appointment_token=appt_token,
            patient_id=test_user.id,
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            appointment_date=date.today(),
            appointment_time=time(10, 0),
            status="scheduled",
        )
        session.add(appt)
        await session.flush()

        # 5. Queue entry
        queue_entry = QueueEntry(
            appointment_id=appt.id,
            hospital_id=hospital.id,
            doctor_id=doctor.id,
            patient_id=test_user.id,
            queue_date=date.today(),
            token_number=1,
            position=1,
            status="waiting",
            estimated_wait_minutes=15,
        )
        session.add(queue_entry)
        await session.commit()

        # Reload with relationships
        res = await session.execute(
            select(Appointment).where(Appointment.id == appt.id)
        )
        saved_appt = res.scalar_one()

        res_q = await session.execute(
            select(QueueEntry).where(QueueEntry.id == queue_entry.id)
        )
        saved_queue = res_q.scalar_one()

        data = {
            "doctor_user_id": doc_user.id,
            "hospital_id": hospital.id,
            "doctor_id": doctor.id,
            "appointment": saved_appt,
            "queue_entry": saved_queue,
        }

    yield data

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == data["doctor_user_id"]))
        await session.execute(delete(Hospital).where(Hospital.id == data["hospital_id"]))
        await session.commit()


# -----------------------------------------------------------------------------
# Unit Tests: Validation and Metadata Sanitization
# -----------------------------------------------------------------------------

def test_sanitize_metadata_removes_sensitive_keys():
    """Verify passwords, tokens, credit cards, and raw secrets are stripped."""
    raw = {
        "appointment_id": str(uuid.uuid4()),
        "password": "supersecretpassword",
        "ACCESS_TOKEN": "eyJhbGciOi...",
        "secret_key": "rawsecret123",
        "notes": "Sensitive doctor notes",
        "cancellation_reason": "Personal medical condition",
        "public_flag": True,
        "token_number": 12,
    }

    sanitized = sanitize_metadata(raw)
    assert "password" not in sanitized
    assert "ACCESS_TOKEN" not in sanitized
    assert "secret_key" not in sanitized
    assert "notes" not in sanitized
    assert "cancellation_reason" not in sanitized
    assert sanitized["token_number"] == 12
    assert sanitized["public_flag"] is True


def test_sanitize_metadata_serializes_complex_types():
    """Verify UUID, date, datetime, and time objects are converted to ISO strings."""
    test_uuid = uuid.uuid4()
    test_dt = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    test_date = date(2026, 10, 26)
    test_time = time(14, 30)

    raw = {
        "uuid_field": test_uuid,
        "datetime_field": test_dt,
        "date_field": test_date,
        "time_field": test_time,
    }

    sanitized = sanitize_metadata(raw)
    assert sanitized["uuid_field"] == str(test_uuid)
    assert sanitized["datetime_field"] == test_dt.isoformat()
    assert sanitized["date_field"] == test_date.isoformat()
    assert sanitized["time_field"] == test_time.isoformat()


@pytest.mark.asyncio
async def test_validation_rejects_invalid_inputs(test_user):
    """Verify validation raises ValueError for invalid category, urgency, or empty title/body."""
    service = NotificationService()
    async with AsyncSessionLocal() as session:
        # Invalid category
        with pytest.raises(ValueError, match="Invalid notification category"):
            await service.create_notification(
                db=session,
                user_id=test_user.id,
                title="Test",
                message="Test msg",
                category="invalid_category",
            )

        # Invalid urgency
        with pytest.raises(ValueError, match="Invalid notification urgency"):
            await service.create_notification(
                db=session,
                user_id=test_user.id,
                title="Test",
                message="Test msg",
                urgency="super_urgent",
            )

        # Empty title
        with pytest.raises(ValueError, match="title cannot be empty"):
            await service.create_notification(
                db=session,
                user_id=test_user.id,
                title="   ",
                message="Test msg",
            )

        # Empty message
        with pytest.raises(ValueError, match="message cannot be empty"):
            await service.create_notification(
                db=session,
                user_id=test_user.id,
                title="Valid Title",
                message="   ",
            )


# -----------------------------------------------------------------------------
# Integration Tests: Notification Creation & Transactional Behavior
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_notification_creation_and_defaults(test_user):
    """Verify notification creation with defaults: unread, normal urgency, appointment category."""
    async with AsyncSessionLocal() as session:
        result = await notification_service.create_notification(
            db=session,
            user_id=test_user.id,
            title="Appointment Reminder",
            message="Your appointment is tomorrow.",
            auto_commit=True,
        )

        assert isinstance(result, NotificationResult)
        assert result.created is True
        assert result.is_duplicate is False

        notif = result.notification
        assert notif is not None
        assert notif.id is not None
        assert notif.user_id == test_user.id
        assert notif.category == "appointment"
        assert notif.urgency == "normal"
        assert notif.is_read is False
        assert notif.read_at is None
        assert notif.created_at is not None


@pytest.mark.asyncio
async def test_idempotency_duplicate_suppression_preserves_outer_transaction(test_user):
    """
    Verify that an idempotency key duplicate:
    1. Returns is_duplicate=True and the existing notification.
    2. Does NOT abort or break the outer database transaction.
    """
    async with AsyncSessionLocal() as session:
        key = f"appt_confirm_{uuid.uuid4().hex[:8]}"

        # 1. First insertion
        res1 = await notification_service.create_notification(
            db=session,
            user_id=test_user.id,
            title="First Attempt",
            message="Initial notification",
            idempotency_key=key,
        )
        assert res1.created is True
        assert res1.is_duplicate is False
        first_id = res1.notification.id

        # 2. Second duplicate insertion within same transaction
        res2 = await notification_service.create_notification(
            db=session,
            user_id=test_user.id,
            title="Duplicate Attempt",
            message="Duplicate notification text",
            idempotency_key=key,
        )
        assert res2.created is False
        assert res2.is_duplicate is True
        assert res2.notification is not None
        assert res2.notification.id == first_id

        # 3. Outer transaction remains healthy and can perform further operations
        res3 = await notification_service.create_notification(
            db=session,
            user_id=test_user.id,
            title="Subsequent Notification",
            message="Subsequent message",
            idempotency_key=f"unique_{uuid.uuid4().hex[:8]}",
        )
        assert res3.created is True

        # Commit successfully
        await session.commit()


@pytest.mark.asyncio
async def test_different_users_can_share_idempotency_key():
    """Verify distinct users can receive notifications derived from the same domain event."""
    async with AsyncSessionLocal() as session:
        user1 = User(
            email=f"usr1_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="User 1",
            role="patient",
        )
        user2 = User(
            email=f"usr2_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="User 2",
            role="patient",
        )
        session.add_all([user1, user2])
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)
        u1_id, u2_id = user1.id, user2.id

        shared_event_key = f"broadcast_event_{uuid.uuid4().hex[:8]}"

        # User 1 notification
        res1 = await notification_service.create_notification(
            db=session,
            user_id=u1_id,
            title="System Alert",
            message="Clinic maintenance notice",
            category="system",
            idempotency_key=shared_event_key,
        )
        assert res1.created is True

        # User 2 notification with SAME idempotency key must succeed
        res2 = await notification_service.create_notification(
            db=session,
            user_id=u2_id,
            title="System Alert",
            message="Clinic maintenance notice",
            category="system",
            idempotency_key=shared_event_key,
        )
        assert res2.created is True
        await session.commit()

        # Cleanup
        await session.execute(delete(User).where(User.id.in_([u1_id, u2_id])))
        await session.commit()


@pytest.mark.asyncio
async def test_transaction_rollback_reverts_notifications(test_user):
    """Verify if the caller rolls back the session, the notification is not persisted."""
    async with AsyncSessionLocal() as session:
        res = await notification_service.create_notification(
            db=session,
            user_id=test_user.id,
            title="Temporary Alert",
            message="This should be rolled back",
            auto_commit=False,
        )
        notif_id = res.notification.id

        # Explicitly roll back caller transaction
        await session.rollback()

    # Verify not in database
    async with AsyncSessionLocal() as session:
        check = await session.execute(
            select(Notification).where(Notification.id == notif_id)
        )
        assert check.scalar_one_or_none() is None


# -----------------------------------------------------------------------------
# Integration Tests: Domain Event Helpers
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_domain_event_helpers(test_appointment_and_queue):
    """Verify domain helpers generate correct titles, urgency levels, and sanitized metadata."""
    appt = test_appointment_and_queue["appointment"]
    queue_entry = test_appointment_and_queue["queue_entry"]

    async with AsyncSessionLocal() as session:
        # 1. Appointment Booked
        res_booked = await notification_service.create_appointment_booked_notification(
            db=session,
            appointment=appt,
        )
        assert res_booked.created is True
        assert res_booked.notification.category == "appointment"
        assert res_booked.notification.urgency == "normal"
        assert "scheduled" in res_booked.notification.message

        # 2. Queue Checked In
        res_checkin = await notification_service.create_queue_checked_in_notification(
            db=session,
            queue_entry=queue_entry,
        )
        assert res_checkin.created is True
        assert res_checkin.notification.category == "queue"
        assert "Q-001" in res_checkin.notification.message

        # 3. Patient Called (Urgent)
        res_called = await notification_service.create_queue_called_notification(
            db=session,
            queue_entry=queue_entry,
        )
        assert res_called.created is True
        assert res_called.notification.urgency == "urgent"
        assert "Your Turn" in res_called.notification.title

        # 4. Consultation Completed
        res_completed = await notification_service.create_queue_completed_notification(
            db=session,
            queue_entry=queue_entry,
        )
        assert res_completed.created is True
        assert res_completed.notification.urgency == "low"

        # 5. Skipped / No-show
        res_skipped = await notification_service.create_queue_skipped_notification(
            db=session,
            queue_entry=queue_entry,
        )
        assert res_skipped.created is True
        assert res_skipped.notification.urgency == "high"

        # 6. Appointment Cancelled
        res_cancelled = await notification_service.create_appointment_cancelled_notification(
            db=session,
            appointment=appt,
            reason="Patient requested reschedule",
        )
        assert res_cancelled.created is True
        assert res_cancelled.notification.urgency == "high"
        assert "Patient requested reschedule" in res_cancelled.notification.message

        await session.commit()
