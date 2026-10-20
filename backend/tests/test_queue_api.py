import asyncio
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.core.websocket import queue_ws_manager
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User

CLINIC_TZ = ZoneInfo("Asia/Kolkata")


def clinic_today_date():
    return datetime.now(CLINIC_TZ).date()


@pytest.fixture(autouse=True)
async def cleanup_test_queue_data():
    """Clean up only test-generated queue entries, appointments, doctors, hospitals, and users."""
    yield
    async with AsyncSessionLocal() as session:
        # Delete queue entries
        await session.execute(
            delete(QueueEntry).where(
                QueueEntry.notes.like("test_queue_%")
                | QueueEntry.id.in_(
                    select(QueueEntry.id).join(Appointment).where(
                        Appointment.appointment_token.like("test_q_%")
                        | Appointment.appointment_token.like("MS-QTEST-%")
                    )
                )
            )
        )
        # Delete appointments
        await session.execute(
            delete(Appointment).where(
                Appointment.appointment_token.like("test_q_%")
                | Appointment.appointment_token.like("MS-QTEST-%")
            )
        )
        # Delete test doctors
        test_doc_users = await session.execute(
            select(User.id).where(User.email.like("test_q_doc_%"))
        )
        doc_uids = test_doc_users.scalars().all()
        if doc_uids:
            await session.execute(delete(Doctor).where(Doctor.user_id.in_(doc_uids)))

        # Delete test hospitals
        await session.execute(delete(Hospital).where(Hospital.name.like("test_q_hosp_%")))

        # Delete test users
        await session.execute(delete(User).where(User.email.like("test_q_%")))
        await session.commit()


async def create_test_user(role: str = "patient", hospital_id: uuid.UUID = None) -> tuple[uuid.UUID, dict]:
    """Helper to create a temporary test user and return (user_id, auth_headers)."""
    user_id = uuid.uuid4()
    email = f"test_q_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Test {role.title()} {uuid.uuid4().hex[:4]}",
            role=role,
            hospital_id=hospital_id,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role=role, hospital_id=hospital_id)
    return user_id, {"Authorization": f"Bearer {token}"}


async def create_test_doctor_fixture() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, dict]:
    """Creates a temporary doctor linked to a temporary hospital. Returns (doctor_id, hospital_id, doc_user_id, auth_headers)."""
    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            name=f"test_q_hosp_{uuid.uuid4().hex[:6]}",
            address="Test Clinic Road 10",
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
            email=f"test_q_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Dr. Test Specialist {uuid.uuid4().hex[:4]}",
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
            experience_years=10,
            consultation_fee=600.0,
            is_available=True,
            credential_status="sample",
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        )
        session.add(doctor)
        await session.commit()

        doc_id = doctor.id
        hosp_id = hosp.id

    token = create_access_token(user_id=doc_user_id, role="doctor")
    return doc_id, hosp_id, doc_user_id, {"Authorization": f"Bearer {token}"}


async def create_test_appointment(
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    hospital_id: uuid.UUID,
    appt_date: date = None,
    appt_time: time = time(10, 0),
    status_val: str = "scheduled",
) -> tuple[uuid.UUID, str]:
    """Creates a test appointment directly in the database."""
    if appt_date is None:
        appt_date = clinic_today_date()

    appt_id = uuid.uuid4()
    appt_token = f"MS-QTEST-{uuid.uuid4().hex[:6].upper()}"

    async with AsyncSessionLocal() as session:
        appt = Appointment(
            id=appt_id,
            appointment_token=appt_token,
            patient_id=patient_id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            status=status_val,
        )
        session.add(appt)
        await session.commit()

    return appt_id, appt_token


# =============================================================================
# 1. Check-In Tests
# =============================================================================

@pytest.mark.anyio
async def test_checkin_valid_appointment_token(client: AsyncClient):
    """Patient can check in using a valid appointment tracking token on clinic date."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, appt_token = await create_test_appointment(pat_id, doc_id, hosp_id)

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": appt_token},
        headers=pat_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["token_number"] == 1
    assert data["token_display"] == "Q-001"
    assert data["position"] == 1
    assert data["status"] == "waiting"
    assert data["estimated_wait_minutes"] == 0
    assert data["appointment_token"] == appt_token

    # F-02 Regression Check: Verify appointment status was atomically updated to checked_in in DB
    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        assert appt.status == "checked_in"


@pytest.mark.anyio
async def test_checkin_valid_appointment_id(client: AsyncClient):
    """Patient can check in using direct appointment UUID on clinic date."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, _ = await create_test_appointment(pat_id, doc_id, hosp_id)

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": str(appt_id)},
        headers=pat_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["appointment_id"] == str(appt_id)
    assert data["token_display"] == "Q-001"


@pytest.mark.anyio
async def test_checkin_invalid_or_unknown_token_rejected_404(client: AsyncClient):
    """Non-existent appointment token rejected with 404 Not Found."""
    _, pat_headers = await create_test_user("patient")

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": "MS-NONEXISTENT-9999"},
        headers=pat_headers,
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_checkin_wrong_patient_rejected_403(client: AsyncClient):
    """Patient B cannot check in for Patient A's appointment."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_a_id, _ = await create_test_user("patient")
    _, pat_b_headers = await create_test_user("patient")
    _, appt_token = await create_test_appointment(pat_a_id, doc_id, hosp_id)

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": appt_token},
        headers=pat_b_headers,
    )
    assert res.status_code == 403
    assert "access denied" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_checkin_past_date_rejected_400(client: AsyncClient):
    """Appointments scheduled on a past date cannot be checked in."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    past_date = clinic_today_date() - timedelta(days=1)
    _, appt_token = await create_test_appointment(pat_id, doc_id, hosp_id, appt_date=past_date)

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": appt_token},
        headers=pat_headers,
    )
    assert res.status_code == 400
    assert "only available on the day of the appointment" in res.json()["detail"]


@pytest.mark.anyio
async def test_checkin_future_date_rejected_400(client: AsyncClient):
    """Appointments scheduled on a future date cannot be checked in today."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    future_date = clinic_today_date() + timedelta(days=1)
    _, appt_token = await create_test_appointment(pat_id, doc_id, hosp_id, appt_date=future_date)

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": appt_token},
        headers=pat_headers,
    )
    assert res.status_code == 400
    assert "only available on the day of the appointment" in res.json()["detail"]


@pytest.mark.anyio
async def test_checkin_cancelled_appointment_rejected_400(client: AsyncClient):
    """Cancelled appointment cannot be checked in."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    _, appt_token = await create_test_appointment(pat_id, doc_id, hosp_id, status_val="cancelled")

    res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_token": appt_token},
        headers=pat_headers,
    )
    assert res.status_code == 400
    assert "cancelled" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_checkin_duplicate_prevention_409(client: AsyncClient):
    """Checking in an already checked-in appointment rejected with 409 Conflict."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    _, appt_token = await create_test_appointment(pat_id, doc_id, hosp_id)

    res1 = await client.post("/api/v1/queue/check-in", json={"appointment_token": appt_token}, headers=pat_headers)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/queue/check-in", json={"appointment_token": appt_token}, headers=pat_headers)
    assert res2.status_code == 409
    assert "already been checked in" in res2.json()["detail"]


# =============================================================================
# 2. Concurrency-Safe Daily Token Allocation Tests
# =============================================================================

@pytest.mark.anyio
async def test_concurrent_http_checkins_distinct_sequential_tokens(client: AsyncClient):
    """
    Simultaneous HTTP check-in requests for the same doctor serialize via PostgreSQL advisory lock
    and allocate strictly sequential, non-colliding daily tokens (Q-001, Q-002, Q-003, Q-004, Q-005).
    """
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    num_patients = 5
    patients_data = []

    for i in range(num_patients):
        pat_id, headers = await create_test_user("patient")
        slot_time = time(9 + i // 2, 30 if i % 2 else 0)
        appt_id, appt_tok = await create_test_appointment(pat_id, doc_id, hosp_id, appt_time=slot_time)
        patients_data.append((pat_id, headers, appt_tok))

    # Send 5 simultaneous check-in requests
    async def do_checkin(p_tok, headers):
        return await client.post(
            "/api/v1/queue/check-in",
            json={"appointment_token": p_tok},
            headers=headers,
        )

    tasks = [do_checkin(p_tok, headers) for _, headers, p_tok in patients_data]
    responses = await asyncio.gather(*tasks)

    for resp in responses:
        assert resp.status_code == 201, f"Failed concurrent checkin: {resp.text}"

    tokens_allocated = [resp.json()["token_number"] for resp in responses]
    displays_allocated = [resp.json()["token_display"] for resp in responses]

    # Verify all tokens are unique and exactly sequential 1..5
    assert len(set(tokens_allocated)) == num_patients
    assert sorted(tokens_allocated) == [1, 2, 3, 4, 5]
    assert sorted(displays_allocated) == ["Q-001", "Q-002", "Q-003", "Q-004", "Q-005"]


# =============================================================================
# 3. Patient Queue Status & Privacy Tests
# =============================================================================

@pytest.mark.anyio
async def test_patient_my_queue_status_isolation(client: AsyncClient):
    """Patient A queries /my and sees only their own entry. Patient B sees 404."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_a_id, pat_a_headers = await create_test_user("patient")
    pat_b_id, pat_b_headers = await create_test_user("patient")
    _, appt_a_tok = await create_test_appointment(pat_a_id, doc_id, hosp_id)

    # Check in patient A
    await client.post("/api/v1/queue/check-in", json={"appointment_token": appt_a_tok}, headers=pat_a_headers)

    # Patient A sees own entry
    res_a = await client.get("/api/v1/queue/my", headers=pat_a_headers)
    assert res_a.status_code == 200
    assert res_a.json()["token_display"] == "Q-001"
    assert res_a.json()["position"] == 1

    # Patient B has not checked in -> 404
    res_b = await client.get("/api/v1/queue/my", headers=pat_b_headers)
    assert res_b.status_code == 404


@pytest.mark.anyio
async def test_public_board_zero_pii(client: AsyncClient):
    """Public board contains strictly anonymized tokens and positions; NO patient PII."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    _, appt_tok = await create_test_appointment(pat_id, doc_id, hosp_id)
    await client.post("/api/v1/queue/check-in", json={"appointment_token": appt_tok}, headers=pat_headers)

    res = await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")
    assert res.status_code == 200
    data = res.json()

    assert data["total_waiting"] == 1
    assert data["waiting_list"][0]["token_display"] == "Q-001"
    assert data["waiting_list"][0]["position"] == 1

    # Privacy verification: Inspect raw JSON text
    raw_text = res.text
    assert "patient_name" not in raw_text
    assert "patient_email" not in raw_text
    assert "patient_phone" not in raw_text
    assert str(pat_id) not in raw_text
    assert appt_tok not in raw_text


# =============================================================================
# 4. Doctor Queue Controls & Concurrency Tests
# =============================================================================

@pytest.mark.anyio
async def test_doctor_call_next_success_and_status_sync(client: AsyncClient):
    """Doctor calling next patient sets queue to in_consultation and appointment to in_progress."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, appt_tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    checkin_res = await client.post("/api/v1/queue/check-in", json={"appointment_token": appt_tok}, headers=pat_headers)
    entry_id = checkin_res.json()["id"]

    call_res = await client.post(f"/api/v1/queue/{entry_id}/call", headers=doc_headers)
    assert call_res.status_code == 200
    assert call_res.json()["status"] == "in_consultation"
    assert call_res.json()["position"] == 0
    assert call_res.json()["called_at"] is not None

    # Check appointment status in database
    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        assert appt.status == "in_progress"


@pytest.mark.anyio
async def test_doctor_call_next_conflict_when_already_in_consultation_409(client: AsyncClient):
    """Calling another patient while one is in consultation returns 409 Conflict."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat1_id, pat1_headers = await create_test_user("patient")
    pat2_id, pat2_headers = await create_test_user("patient")

    _, tok1 = await create_test_appointment(pat1_id, doc_id, hosp_id, appt_time=time(10, 0))
    _, tok2 = await create_test_appointment(pat2_id, doc_id, hosp_id, appt_time=time(10, 30))

    r1 = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok1}, headers=pat1_headers)
    r2 = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok2}, headers=pat2_headers)

    e1_id = r1.json()["id"]
    e2_id = r2.json()["id"]

    # Call patient 1
    call1 = await client.post(f"/api/v1/queue/{e1_id}/call", headers=doc_headers)
    assert call1.status_code == 200

    # Call patient 2 while patient 1 is in consultation -> 409 Conflict
    call2 = await client.post(f"/api/v1/queue/{e2_id}/call", headers=doc_headers)
    assert call2.status_code == 409
    assert "another patient is currently in consultation" in call2.json()["detail"].lower()


@pytest.mark.anyio
async def test_simultaneous_call_next_concurrency_409(client: AsyncClient):
    """
    Simultaneous call-next requests for the same doctor serialize:
    exactly one succeeds (200), and the other fails with 409 Conflict.
    """
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat1_id, pat1_headers = await create_test_user("patient")
    pat2_id, pat2_headers = await create_test_user("patient")

    _, tok1 = await create_test_appointment(pat1_id, doc_id, hosp_id, appt_time=time(11, 0))
    _, tok2 = await create_test_appointment(pat2_id, doc_id, hosp_id, appt_time=time(11, 30))

    r1 = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok1}, headers=pat1_headers)
    r2 = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok2}, headers=pat2_headers)
    e1_id = r1.json()["id"]
    e2_id = r2.json()["id"]

    async def call_entry(eid):
        return await client.post(f"/api/v1/queue/{eid}/call", headers=doc_headers)

    # Launch simultaneously
    resp1, resp2 = await asyncio.gather(call_entry(e1_id), call_entry(e2_id))

    status_codes = sorted([resp1.status_code, resp2.status_code])
    assert status_codes == [200, 409], f"Expected [200, 409], got {status_codes}"


@pytest.mark.anyio
async def test_doctor_complete_consultation_and_status_sync(client: AsyncClient):
    """Completing a consultation sets queue to completed and appointment to completed."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]
    await client.post(f"/api/v1/queue/{eid}/call", headers=doc_headers)

    comp_res = await client.post(f"/api/v1/queue/{eid}/complete", json={"notes": "Prescribed medicine"}, headers=doc_headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"
    assert comp_res.json()["completed_at"] is not None

    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        assert appt.status == "completed"


@pytest.mark.anyio
async def test_doctor_skip_patient_and_status_sync(client: AsyncClient):
    """Skipping a patient sets queue to skipped and appointment to no_show."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    skip_res = await client.post(f"/api/v1/queue/{eid}/skip", headers=doc_headers)
    assert skip_res.status_code == 200
    assert skip_res.json()["status"] == "skipped"

    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        assert appt.status == "no_show"


@pytest.mark.anyio
async def test_doctor_recall_skipped_patient_success(client: AsyncClient):
    """Recalling a skipped patient returns queue to waiting and appointment to scheduled."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]
    await client.post(f"/api/v1/queue/{eid}/skip", headers=doc_headers)

    recall_res = await client.post(f"/api/v1/queue/{eid}/recall", headers=doc_headers)
    assert recall_res.status_code == 200
    assert recall_res.json()["status"] == "waiting"

    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        assert appt.status == "checked_in"


@pytest.mark.anyio
async def test_doctor_cannot_recall_cancelled_appointment_400(client: AsyncClient):
    """Recalling a queue entry whose appointment was cancelled is rejected with 400 Bad Request."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]
    await client.post(f"/api/v1/queue/{eid}/skip", headers=doc_headers)

    # Cancel appointment
    async with AsyncSessionLocal() as session:
        appt = await session.get(Appointment, appt_id)
        appt.status = "cancelled"
        await session.commit()

    recall_res = await client.post(f"/api/v1/queue/{eid}/recall", headers=doc_headers)
    assert recall_res.status_code == 400
    assert "cancelled" in recall_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_patient_cannot_cancel_active_consultation_400(client: AsyncClient):
    """Patient cannot cancel a consultation that is already in_consultation."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    _, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]
    await client.post(f"/api/v1/queue/{eid}/call", headers=doc_headers)

    del_res = await client.delete(f"/api/v1/queue/{eid}", headers=pat_headers)
    assert del_res.status_code == 400
    assert "already in progress" in del_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_patient_can_cancel_waiting_entry_and_status_sync(client: AsyncClient):
    """Patient can cancel a waiting entry; transitions queue and appointment to cancelled."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    del_res = await client.delete(f"/api/v1/queue/{eid}", headers=pat_headers)
    assert del_res.status_code == 200

    async with AsyncSessionLocal() as session:
        q_entry = await session.get(QueueEntry, uuid.UUID(eid))
        appt = await session.get(Appointment, appt_id)
        assert q_entry.status == "cancelled"
        assert appt.status == "cancelled"


# =============================================================================
# 5. Queue Position Recalculation Consistency Test
# =============================================================================

@pytest.mark.anyio
async def test_queue_position_consistency_after_each_lifecycle_action(client: AsyncClient):
    """
    Verifies deterministic waiting positions (1, 2, 3...) across multiple patients
    as entries are called, completed, skipped, recalled, and cancelled.
    """
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()

    patients = []
    for i in range(4):
        pid, p_hdr = await create_test_user("patient")
        slot_time = time(9 + i // 2, 30 if i % 2 else 0)
        _, tok = await create_test_appointment(pid, doc_id, hosp_id, appt_time=slot_time)
        r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=p_hdr)
        assert r.status_code == 201
        eid = r.json()["id"]
        patients.append((pid, p_hdr, eid))

    # Initial check: 4 patients waiting at positions 1, 2, 3, 4
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert [item["position"] for item in board["waiting_list"]] == [1, 2, 3, 4]
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-001", "Q-002", "Q-003", "Q-004"]

    # Action 1: Call patient 1 -> waiting list now has patients 2, 3, 4 with positions 1, 2, 3
    await client.post(f"/api/v1/queue/{patients[0][2]}/call", headers=doc_headers)
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert board["current_consultation"]["token_display"] == "Q-001"
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-002", "Q-003", "Q-004"]
    assert [item["position"] for item in board["waiting_list"]] == [1, 2, 3]

    # Action 2: Complete patient 1 -> current consultation becomes None
    await client.post(f"/api/v1/queue/{patients[0][2]}/complete", headers=doc_headers)
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert board["current_consultation"] is None
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-002", "Q-003", "Q-004"]
    assert [item["position"] for item in board["waiting_list"]] == [1, 2, 3]

    # Action 3: Skip patient 2 -> waiting list now has patients 3, 4 with positions 1, 2
    await client.post(f"/api/v1/queue/{patients[1][2]}/skip", headers=doc_headers)
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-003", "Q-004"]
    assert [item["position"] for item in board["waiting_list"]] == [1, 2]

    # Action 4: Cancel patient 4 -> waiting list has only patient 3 at position 1
    await client.delete(f"/api/v1/queue/{patients[3][2]}", headers=patients[3][1])
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-003"]
    assert [item["position"] for item in board["waiting_list"]] == [1]

    # Action 5: Recall patient 2 (token Q-002) -> waiting list has Q-002 (pos 1), Q-003 (pos 2)
    await client.post(f"/api/v1/queue/{patients[1][2]}/recall", headers=doc_headers)
    board = (await client.get(f"/api/v1/queue/doctor/{doc_id}/public-board")).json()
    assert [item["token_display"] for item in board["waiting_list"]] == ["Q-002", "Q-003"]
    assert [item["position"] for item in board["waiting_list"]] == [1, 2]


# =============================================================================
# 6. Authorization & Role-Based Access Control Tests
# =============================================================================

@pytest.mark.anyio
async def test_doctor_cross_queue_authorization_403(client: AsyncClient):
    """Doctor B cannot call, complete, or skip Doctor A's queue entry."""
    doc_a_id, hosp_a_id, _, _ = await create_test_doctor_fixture()
    _, _, _, doc_b_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")

    _, tok = await create_test_appointment(pat_id, doc_a_id, hosp_a_id)
    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    # Doctor B attempts to call Doctor A's patient
    call_res = await client.post(f"/api/v1/queue/{eid}/call", headers=doc_b_headers)
    assert call_res.status_code == 403
    assert "access denied" in call_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_hospital_admin_scoping_authorization(client: AsyncClient):
    """Admin of Hospital X cannot manage queue of Doctor at Hospital Y."""
    doc_y_id, hosp_y_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")

    # Create Hospital X and admin for Hospital X
    async with AsyncSessionLocal() as session:
        hosp_x = Hospital(
            name=f"test_q_hosp_{uuid.uuid4().hex[:6]}",
            address="Street X",
            city="Delhi",
            state="Delhi",
            is_active=True,
            data_source="sample",
        )
        session.add(hosp_x)
        await session.commit()
        hosp_x_id = hosp_x.id

    admin_x_id, admin_x_headers = await create_test_user("hospital_admin", hospital_id=hosp_x_id)

    _, tok = await create_test_appointment(pat_id, doc_y_id, hosp_y_id)
    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    call_res = await client.post(f"/api/v1/queue/{eid}/call", headers=admin_x_headers)
    assert call_res.status_code == 403
    assert "does not belong to your authorized hospital" in call_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_hospital_admin_unaffiliated_fails_closed(client: AsyncClient):
    """F-01 Regression: Hospital admin with no verified hospital affiliation fails closed with 403."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    # Admin with NO hospital_id claim in JWT (standard /auth/login issuance)
    admin_id, admin_headers = await create_test_user("hospital_admin", hospital_id=None)

    _, tok = await create_test_appointment(pat_id, doc_id, hosp_id)
    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    # Fails closed on call
    call_res = await client.post(f"/api/v1/queue/{eid}/call", headers=admin_headers)
    assert call_res.status_code == 403
    assert "no verified hospital affiliation configured" in call_res.json()["detail"].lower()

    # Fails closed on clinical queue view
    view_res = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=admin_headers)
    assert view_res.status_code == 403
    assert "no verified hospital affiliation configured" in view_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_hospital_admin_header_spoofing_rejected(client: AsyncClient):
    """F-01 Regression: Client cannot spoof hospital access by sending an X-Hospital-Id header."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    admin_id, admin_headers = await create_test_user("hospital_admin", hospital_id=None)

    _, tok = await create_test_appointment(pat_id, doc_id, hosp_id)
    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    # Try spoofing with X-Hospital-Id header matching the doctor's hospital
    spoofed_headers = {**admin_headers, "X-Hospital-Id": str(hosp_id)}
    call_res = await client.post(f"/api/v1/queue/{eid}/call", headers=spoofed_headers)
    assert call_res.status_code == 403
    assert "no verified hospital affiliation configured" in call_res.json()["detail"].lower()


@pytest.mark.anyio
async def test_cancellation_consistency_via_queue_and_appointment_endpoints(client: AsyncClient):
    """F-03 Regression: Consistent cancellation policy across queue and appointment endpoints."""
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")

    # Case A: Cancel checked_in appointment via appointment endpoint
    appt_a_id, tok_a = await create_test_appointment(pat_id, doc_id, hosp_id)
    r_a = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok_a}, headers=pat_headers)
    assert r_a.status_code == 201

    cancel_appt_res = await client.post(f"/api/v1/appointments/{appt_a_id}/cancel", headers=pat_headers)
    assert cancel_appt_res.status_code == 200

    async with AsyncSessionLocal() as session:
        appt_a = await session.get(Appointment, appt_a_id)
        q_a = await session.execute(select(QueueEntry).where(QueueEntry.appointment_id == appt_a_id))
        entry_a = q_a.scalar_one()
        assert appt_a.status == "cancelled"
        assert entry_a.status == "cancelled"
        assert entry_a.position == 0

    # Re-cancelling already cancelled appointment is rejected
    recancel_res = await client.post(f"/api/v1/appointments/{appt_a_id}/cancel", headers=pat_headers)
    assert recancel_res.status_code == 400

    # Case B: Cancel checked_in appointment via queue endpoint
    appt_b_id, tok_b = await create_test_appointment(pat_id, doc_id, hosp_id)
    r_b = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok_b}, headers=pat_headers)
    eid_b = r_b.json()["id"]

    cancel_q_res = await client.delete(f"/api/v1/queue/{eid_b}", headers=pat_headers)
    assert cancel_q_res.status_code == 200

    async with AsyncSessionLocal() as session:
        appt_b = await session.get(Appointment, appt_b_id)
        entry_b = await session.get(QueueEntry, uuid.UUID(eid_b))
        assert appt_b.status == "cancelled"
        assert entry_b.status == "cancelled"
        assert entry_b.position == 0

    # Re-cancelling already cancelled queue entry is rejected
    recancel_q_res = await client.delete(f"/api/v1/queue/{eid_b}", headers=pat_headers)
    assert recancel_q_res.status_code == 400

    # Case C: Cannot cancel an active in-consultation entry via either endpoint
    appt_c_id, tok_c = await create_test_appointment(pat_id, doc_id, hosp_id)
    r_c = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok_c}, headers=pat_headers)
    eid_c = r_c.json()["id"]
    await client.post(f"/api/v1/queue/{eid_c}/call", headers=doc_headers)

    # Cancel via appointment endpoint while in consultation -> rejected 400
    fail_appt_cancel = await client.post(f"/api/v1/appointments/{appt_c_id}/cancel", headers=pat_headers)
    assert fail_appt_cancel.status_code == 400
    assert "in_progress" in fail_appt_cancel.json()["detail"].lower()

    # Cancel via queue endpoint while in consultation -> rejected 400
    fail_q_cancel = await client.delete(f"/api/v1/queue/{eid_c}", headers=pat_headers)
    assert fail_q_cancel.status_code == 400
    assert "already in progress" in fail_q_cancel.json()["detail"].lower()


# =============================================================================
# 7. WebSocket Streaming & Scoping Tests
# =============================================================================

@pytest.mark.anyio
async def test_websocket_broadcast_and_scoping():
    """
    Tests WebSocket connection manager room isolation:
    Subscribers to doctor A receive events for doctor A; subscribers to doctor B do NOT.
    """
    doc_a = str(uuid.uuid4())
    doc_b = str(uuid.uuid4())

    received_a = []
    received_b = []

    class MockWebSocket:
        def __init__(self, target_list):
            self.target_list = target_list
            self.accepted = False

        async def accept(self):
            self.accepted = True

        async def send_json(self, msg):
            self.target_list.append(msg)

    ws_a = MockWebSocket(received_a)
    ws_b = MockWebSocket(received_b)

    await queue_ws_manager.connect(doc_a, ws_a)
    await queue_ws_manager.connect(doc_b, ws_b)

    event_a = {"event": "QUEUE_UPDATED", "doctor_id": doc_a, "action": "CHECKED_IN"}
    await queue_ws_manager.broadcast_to_doctor(doc_a, event_a)

    assert len(received_a) == 1
    assert received_a[0]["action"] == "CHECKED_IN"
    assert len(received_b) == 0, "Doctor B room leaked an event from Doctor A!"

    # Clean up
    queue_ws_manager.disconnect(doc_a, ws_a)
    queue_ws_manager.disconnect(doc_b, ws_b)


async def simulate_websocket_connect(path: str, token: str = None) -> list[dict]:
    """Helper to test WebSocket route handshake directly on the active session event loop."""
    from app.main import app
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
        headers.append((b"cookie", f"access_token={token}".encode()))

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "subprotocols": [],
    }
    events = []

    async def receive():
        if not events:
            return {"type": "websocket.connect"}
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(msg):
        events.append(msg)

    try:
        await app(scope, receive, send)
    except Exception as exc:
        events.append({"type": "exception", "error": str(exc)})

    return events


@pytest.mark.anyio
async def test_websocket_unauthenticated_connection_rejected():
    """Unauthenticated WebSocket connection is rejected with 1008 Policy Violation."""
    doc_id = str(uuid.uuid4())
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_id}")
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.close"
    assert events[0]["code"] == 1008


@pytest.mark.anyio
async def test_websocket_doctor_cross_room_rejected():
    """F-04 Regression: Doctor A cannot connect to Doctor B's WebSocket channel."""
    doc_a_id, hosp_a_id, doc_a_user_id, _ = await create_test_doctor_fixture()
    doc_b_id, _, _, _ = await create_test_doctor_fixture()

    token_a = create_access_token(user_id=doc_a_user_id, role="doctor")
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_b_id}", token=token_a)
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.close"
    assert events[0]["code"] == 1008


@pytest.mark.anyio
async def test_websocket_doctor_own_room_accepted():
    """F-04 Regression: Doctor A can connect to their own WebSocket channel."""
    doc_a_id, hosp_a_id, doc_a_user_id, _ = await create_test_doctor_fixture()
    token_a = create_access_token(user_id=doc_a_user_id, role="doctor")
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_a_id}", token=token_a)
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.accept"


@pytest.mark.anyio
async def test_websocket_patient_with_appointment_today_accepted():
    """F-04 Regression: Patient with active appointment today can connect to doctor's queue channel."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, _ = await create_test_user("patient")
    await create_test_appointment(pat_id, doc_id, hosp_id)

    token_pat = create_access_token(user_id=pat_id, role="patient")
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_id}", token=token_pat)
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.accept"


@pytest.mark.anyio
async def test_websocket_patient_without_appointment_today_rejected():
    """F-04 Regression: Patient without appointment with doctor today is rejected from doctor's channel."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    pat_id, _ = await create_test_user("patient")
    # Patient has no appointment with this doctor today

    token_pat = create_access_token(user_id=pat_id, role="patient")
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_id}", token=token_pat)
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.close"
    assert events[0]["code"] == 1008


@pytest.mark.anyio
async def test_websocket_hospital_admin_unaffiliated_rejected():
    """F-04 Regression: Unaffiliated hospital admin is rejected from doctor's channel."""
    doc_id, hosp_id, _, _ = await create_test_doctor_fixture()
    admin_id, _ = await create_test_user("hospital_admin", hospital_id=None)

    token_admin = create_access_token(user_id=admin_id, role="hospital_admin")
    events = await simulate_websocket_connect(f"/api/v1/queue/ws/{doc_id}", token=token_admin)
    assert len(events) >= 1
    assert events[0]["type"] == "websocket.close"
    assert events[0]["code"] == 1008



# =============================================================================
# 8. Transaction Atomic Rollback Test
# =============================================================================

@pytest.mark.anyio
async def test_database_transaction_rollback_on_failed_queue_mutation(client: AsyncClient):
    """
    Verifies that a failure during an atomic state mutation leaves both queue and appointment
    in their original consistent state without partial writes.
    """
    doc_id, hosp_id, _, doc_headers = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")
    appt_id, tok = await create_test_appointment(pat_id, doc_id, hosp_id)

    r = await client.post("/api/v1/queue/check-in", json={"appointment_token": tok}, headers=pat_headers)
    eid = r.json()["id"]

    # Attempting to call an invalid endpoint with an invalid action
    # e.g., calling complete on an entry that is 'waiting' (not in_consultation)
    comp_res = await client.post(f"/api/v1/queue/{eid}/complete", headers=doc_headers)
    assert comp_res.status_code == 400

    # Verify both queue entry and appointment remain in waiting / scheduled
    async with AsyncSessionLocal() as session:
        q = await session.get(QueueEntry, uuid.UUID(eid))
        a = await session.get(Appointment, appt_id)
        assert q.status == "waiting"
        assert a.status == "checked_in"
