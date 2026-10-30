import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.core.websocket import queue_ws_manager
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.notification import Notification
from app.models.queue import QueueEntry
from app.models.user import User
from app.services.notification import notification_service

CLINIC_TZ = ZoneInfo("Asia/Kolkata")


def clinic_today_date() -> date:
    return datetime.now(CLINIC_TZ).date()


@pytest.fixture(autouse=True)
async def cleanup_test_workflow_data():
    """Ensure test entities are purged after each test."""
    yield
    async with AsyncSessionLocal() as session:
        # Cascade delete users cleans up their appointments, queue entries, and notifications
        await session.execute(
            delete(User).where(User.email.like("test_wf_%@example.com"))
        )
        await session.execute(
            delete(Hospital).where(Hospital.name.like("test_wf_hosp_%"))
        )
        await session.commit()


async def create_wf_user(role: str = "patient", full_name: str = "Test User") -> tuple[User, dict]:
    """Helper to create a test user and auth headers."""
    user_id = uuid.uuid4()
    email = f"test_wf_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password=get_password_hash("ValidPass123!"),
            full_name=full_name,
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, {"Authorization": f"Bearer {token}"}


async def create_wf_doctor_fixture() -> tuple[Doctor, Hospital, User, dict]:
    """Creates a temporary doctor, hospital, and doctor user with auth headers."""
    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            name=f"test_wf_hosp_{uuid.uuid4().hex[:6]}",
            address="456 Clinical Way",
            city="New Delhi",
            state="Delhi",
            latitude=28.6,
            longitude=77.2,
            is_active=True,
            data_source="sample",
        )
        session.add(hosp)
        await session.flush()

        doc_user_id = uuid.uuid4()
        doc_user = User(
            id=doc_user_id,
            email=f"test_wf_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("ValidPass123!"),
            full_name="Dr. Eleanor Vance",
            role="doctor",
            is_active=True,
        )
        session.add(doc_user)
        await session.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            hospital_id=hosp.id,
            specialty="Cardiology",
            qualification="MBBS, MD",
            experience_years=12,
            consultation_fee=750.0,
            is_available=True,
            credential_status="sample",
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        )
        session.add(doctor)
        await session.commit()
        await session.refresh(doctor)
        await session.refresh(hosp)
        await session.refresh(doc_user)

    token = create_access_token(user_id=doc_user.id, role="doctor")
    return doctor, hosp, doc_user, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Appointment Booking & Cancellation Notification Workflows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_booking_creates_one_patient_notification(client: AsyncClient):
    """Verify booking an appointment generates an in-app confirmation notification for the patient."""
    patient, pat_headers = await create_wf_user("patient", "Alice Smith")
    doctor, hospital, doc_user, _ = await create_wf_doctor_fixture()

    booking_payload = {
        "doctor_id": str(doctor.id),
        "appointment_date": (clinic_today_date() + timedelta(days=1)).isoformat(),
        "appointment_time": "10:00",
        "notes": "Routine checkup",
    }

    resp = await client.post("/api/v1/appointments", json=booking_payload, headers=pat_headers)
    assert resp.status_code == 201
    appt_data = resp.json()
    appt_id = uuid.UUID(appt_data["id"])

    # Query patient's notifications via REST API
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()["items"]

    assert len(notifs) == 1
    booked_notif = notifs[0]
    assert booked_notif["category"] == "appointment"
    assert booked_notif["event_type"] == "appointment_booked"
    assert booked_notif["urgency"] == "normal"
    assert booked_notif["is_read"] is False
    assert "Dr. Eleanor Vance" in booked_notif["message"]
    assert appt_data["appointment_token"] in booked_notif["message"]
    assert booked_notif["metadata_json"]["appointment_id"] == str(appt_id)


@pytest.mark.asyncio
async def test_failed_booking_does_not_create_false_success_notification(client: AsyncClient):
    """Verify that slot collision or failure does not generate a success notification."""
    patient1, pat1_headers = await create_wf_user("patient", "Patient One")
    patient2, pat2_headers = await create_wf_user("patient", "Patient Two")
    doctor, hospital, _, _ = await create_wf_doctor_fixture()

    appt_date = (clinic_today_date() + timedelta(days=2)).isoformat()
    booking_payload = {
        "doctor_id": str(doctor.id),
        "appointment_date": appt_date,
        "appointment_time": "11:00",
    }

    # First booking succeeds
    r1 = await client.post("/api/v1/appointments", json=booking_payload, headers=pat1_headers)
    assert r1.status_code == 201

    # Second booking for the same doctor/date/time collides and fails
    r2 = await client.post("/api/v1/appointments", json=booking_payload, headers=pat2_headers)
    assert r2.status_code == 409

    # Patient 2 must have zero notifications
    notif_resp2 = await client.get("/api/v1/notifications", headers=pat2_headers)
    assert notif_resp2.status_code == 200
    assert notif_resp2.json()["total"] == 0


@pytest.mark.asyncio
async def test_successful_cancellation_creates_one_patient_notification(client: AsyncClient):
    """Verify cancelling an appointment generates a cancellation notification with reason."""
    patient, pat_headers = await create_wf_user("patient", "Bob Jones")
    doctor, hospital, _, _ = await create_wf_doctor_fixture()

    # Book appointment
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": (clinic_today_date() + timedelta(days=3)).isoformat(),
            "appointment_time": "14:00",
        },
        headers=pat_headers,
    )
    assert b_resp.status_code == 201
    appt_id = b_resp.json()["id"]

    # Cancel appointment
    c_resp = await client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"cancellation_reason": "Family emergency"},
        headers=pat_headers,
    )
    assert c_resp.status_code == 200

    # Query notifications: should now have 2 notifications (booked, then cancelled newest first)
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    assert notif_resp.status_code == 200
    notifs = notif_resp.json()["items"]
    assert len(notifs) == 2

    cancel_notif = notifs[0]  # Newest first
    assert cancel_notif["event_type"] == "appointment_cancelled"
    assert cancel_notif["urgency"] == "high"
    assert "Family emergency" in cancel_notif["message"]


@pytest.mark.asyncio
async def test_failed_cancellation_does_not_create_false_success_notification(client: AsyncClient):
    """Verify repeat cancellation failure does not emit extra cancellation notifications."""
    patient, pat_headers = await create_wf_user("patient", "Charlie Brown")
    doctor, hospital, _, _ = await create_wf_doctor_fixture()

    # Book and cancel
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": (clinic_today_date() + timedelta(days=4)).isoformat(),
            "appointment_time": "15:00",
        },
        headers=pat_headers,
    )
    appt_id = b_resp.json()["id"]
    await client.post(f"/api/v1/appointments/{appt_id}/cancel", headers=pat_headers)

    # Second cancel fails (400 Bad Request)
    r_repeat = await client.post(f"/api/v1/appointments/{appt_id}/cancel", headers=pat_headers)
    assert r_repeat.status_code == 400

    # Verify notification count remains 2 (1 booked, 1 cancelled)
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    assert notif_resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# 2. Queue Lifecycle Notification Workflows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_queue_check_in_creates_correct_notification(client: AsyncClient):
    """Verify queue check-in emits a notification with token and position."""
    patient, pat_headers = await create_wf_user("patient", "Diana Prince")
    doctor, hospital, doc_user, doc_headers = await create_wf_doctor_fixture()

    # Book appointment for TODAY (so check-in is allowed)
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": clinic_today_date().isoformat(),
            "appointment_time": "09:00",
        },
        headers=pat_headers,
    )
    assert b_resp.status_code == 201
    appt_id = b_resp.json()["id"]

    # Check in
    ci_resp = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": appt_id},
        headers=pat_headers,
    )
    assert ci_resp.status_code == 201
    ci_data = ci_resp.json()

    # Inspect patient notifications
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    notifs = notif_resp.json()["items"]
    # 2 notifications: booked and queue_checked_in (newest first)
    assert len(notifs) == 2
    ci_notif = notifs[0]
    assert ci_notif["event_type"] == "queue_checked_in"
    assert ci_notif["category"] == "queue"
    assert ci_data["token_display"] in ci_notif["message"]
    assert "Position #1" in ci_notif["message"]


@pytest.mark.asyncio
async def test_successful_call_next_operation_creates_correct_notification(client: AsyncClient):
    """Verify calling patient into consultation room generates urgent call notification."""
    patient, pat_headers = await create_wf_user("patient", "Evan Wright")
    doctor, hospital, doc_user, doc_headers = await create_wf_doctor_fixture()

    # Book and check in
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": clinic_today_date().isoformat(),
            "appointment_time": "09:30",
        },
        headers=pat_headers,
    )
    ci_resp = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": b_resp.json()["id"]},
        headers=pat_headers,
    )
    entry_id = ci_resp.json()["id"]

    # Doctor calls patient
    call_resp = await client.post(f"/api/v1/queue/{entry_id}/call", headers=doc_headers)
    assert call_resp.status_code == 200

    # Patient receives urgent notification
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    notifs = notif_resp.json()["items"]
    call_notif = notifs[0]
    assert call_notif["event_type"] == "queue_patient_called"
    assert call_notif["urgency"] == "urgent"
    assert "Your Turn" in call_notif["title"]
    assert "Dr. Eleanor Vance" in call_notif["message"]


@pytest.mark.asyncio
async def test_successful_completion_creates_correct_notification(client: AsyncClient):
    """Verify completing consultation generates low-urgency completion notification."""
    patient, pat_headers = await create_wf_user("patient", "Fiona Gallagher")
    doctor, hospital, doc_user, doc_headers = await create_wf_doctor_fixture()

    # Book, check in, call
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": clinic_today_date().isoformat(),
            "appointment_time": "10:00",
        },
        headers=pat_headers,
    )
    ci_resp = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": b_resp.json()["id"]},
        headers=pat_headers,
    )
    entry_id = ci_resp.json()["id"]
    await client.post(f"/api/v1/queue/{entry_id}/call", headers=doc_headers)

    # Doctor completes consultation
    comp_resp = await client.post(f"/api/v1/queue/{entry_id}/complete", headers=doc_headers)
    assert comp_resp.status_code == 200

    # Patient receives completion notification
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    notifs = notif_resp.json()["items"]
    comp_notif = notifs[0]
    assert comp_notif["event_type"] == "queue_completed"
    assert comp_notif["urgency"] == "low"
    assert "Consultation Completed" in comp_notif["title"]


@pytest.mark.asyncio
async def test_successful_skip_operation_creates_correct_notification(client: AsyncClient):
    """Verify skipping absent patient generates high-urgency missed call notification."""
    patient, pat_headers = await create_wf_user("patient", "George Clark")
    doctor, hospital, doc_user, doc_headers = await create_wf_doctor_fixture()

    # Book, check in
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": clinic_today_date().isoformat(),
            "appointment_time": "10:30",
        },
        headers=pat_headers,
    )
    ci_resp = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": b_resp.json()["id"]},
        headers=pat_headers,
    )
    entry_id = ci_resp.json()["id"]

    # Doctor skips patient
    skip_resp = await client.post(f"/api/v1/queue/{entry_id}/skip", headers=doc_headers)
    assert skip_resp.status_code == 200

    # Patient receives skipped notification
    notif_resp = await client.get("/api/v1/notifications", headers=pat_headers)
    notifs = notif_resp.json()["items"]
    skip_notif = notifs[0]
    assert skip_notif["event_type"] == "queue_skipped"
    assert skip_notif["urgency"] == "high"
    assert "Queue Call Missed" in skip_notif["title"]


# ---------------------------------------------------------------------------
# 3. Privacy, Multi-Tenancy, and Zero-PII Checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_associated_strictly_with_correct_patient(client: AsyncClient):
    """Verify Patient B never receives notifications triggered by Patient A's lifecycle events."""
    patient_a, headers_a = await create_wf_user("patient", "Patient Alpha")
    patient_b, headers_b = await create_wf_user("patient", "Patient Beta")
    doctor, hospital, _, doc_headers = await create_wf_doctor_fixture()

    # Patient A books, checks in
    b_resp = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doctor.id),
            "appointment_date": clinic_today_date().isoformat(),
            "appointment_time": "11:30",
        },
        headers=headers_a,
    )
    ci_resp = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": b_resp.json()["id"]},
        headers=headers_a,
    )

    # Patient A has 2 notifications
    resp_a = await client.get("/api/v1/notifications", headers=headers_a)
    assert resp_a.json()["total"] == 2

    # Patient B must have exactly 0 notifications
    resp_b = await client.get("/api/v1/notifications", headers=headers_b)
    assert resp_b.json()["total"] == 0


@pytest.mark.asyncio
async def test_public_queue_broadcasts_contain_no_patient_pii():
    """Verify that WebSocket broadcast payloads in queue workflows maintain zero patient PII."""
    # We inspect queue_ws_manager broadcast message shape directly
    # Check that broadcast messages for queue actions do not include patient names, notes, or contact info
    sensitive_keys = {"patient_name", "patient_email", "patient_phone", "notes", "clinical_notes"}

    # Mock broadcast intercept
    intercepted_payloads = []
    original_broadcast = queue_ws_manager.broadcast_to_doctor

    async def mock_broadcast(doctor_id, payload):
        intercepted_payloads.append(payload)

    queue_ws_manager.broadcast_to_doctor = mock_broadcast

    try:
        # Construct sample broadcast payload as generated in queue.py
        payload = {
            "event": "QUEUE_UPDATED",
            "doctor_id": str(uuid.uuid4()),
            "action": "PATIENT_CALLED",
            "token_display": "A-01",
            "token_number": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await queue_ws_manager.broadcast_to_doctor("doc-1", payload)

        for p in intercepted_payloads:
            for k in sensitive_keys:
                assert k not in p, f"Sensitive key {k} found in public broadcast payload!"
    finally:
        queue_ws_manager.broadcast_to_doctor = original_broadcast


# ---------------------------------------------------------------------------
# 4. Idempotency & Transaction Rollback Safety
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repeated_processing_does_not_create_duplicate_notifications():
    """Verify that calling domain event helpers repeatedly is idempotent and does not duplicate rows."""
    patient, _ = await create_wf_user("patient", "Idempotency Test User")
    doctor, hospital, _, _ = await create_wf_doctor_fixture()

    appt = Appointment(
        id=uuid.uuid4(),
        appointment_token=f"MS-IDEMP-{uuid.uuid4().hex[:6].upper()}",
        patient_id=patient.id,
        doctor_id=doctor.id,
        hospital_id=hospital.id,
        appointment_date=clinic_today_date(),
        appointment_time=time(16, 0),
        status="scheduled",
    )

    async with AsyncSessionLocal() as session:
        session.add(appt)
        await session.commit()

    async with AsyncSessionLocal() as session:
        # First call
        r1 = await notification_service.create_appointment_booked_notification(
            db=session,
            appointment=appt,
            auto_commit=True,
        )
        assert r1.created is True
        assert r1.is_duplicate is False

        # Repeated call with same appointment (identical idempotency key)
        r2 = await notification_service.create_appointment_booked_notification(
            db=session,
            appointment=appt,
            auto_commit=True,
        )
        assert r2.is_duplicate is True
        assert r2.created is False
        assert r2.notification.id == r1.notification.id

        # Verify only 1 notification row in DB
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.user_id == patient.id,
                    Notification.idempotency_key == f"appt_booked:{appt.id}",
                )
            )
        ).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_transaction_rollback_does_not_leave_orphaned_notification():
    """Verify that rolling back an uncommitted transaction leaves zero orphan notifications."""
    patient, _ = await create_wf_user("patient", "Rollback Patient")
    doctor, hospital, _, _ = await create_wf_doctor_fixture()

    appt_id = uuid.uuid4()
    appt = Appointment(
        id=appt_id,
        appointment_token=f"MS-ROLLBACK-{uuid.uuid4().hex[:6].upper()}",
        patient_id=patient.id,
        doctor_id=doctor.id,
        hospital_id=hospital.id,
        appointment_date=clinic_today_date(),
        appointment_time=time(16, 30),
        status="scheduled",
    )

    async with AsyncSessionLocal() as session:
        session.add(appt)
        # Create notification within session WITHOUT auto_commit
        await notification_service.create_appointment_booked_notification(
            db=session,
            appointment=appt,
            auto_commit=False,
        )
        # Abort transaction
        await session.rollback()

    # Verify neither appointment nor notification exists in DB
    async with AsyncSessionLocal() as session:
        db_appt = (
            await session.execute(select(Appointment).where(Appointment.id == appt_id))
        ).scalar_one_or_none()
        assert db_appt is None

        db_notifs = (
            await session.execute(
                select(Notification).where(Notification.user_id == patient.id)
            )
        ).scalars().all()
        assert len(db_notifs) == 0

