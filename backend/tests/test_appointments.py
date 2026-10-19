import asyncio
import re
import uuid
from datetime import date, datetime, time, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_test_appointment_data():
    """Non-destructive fixture: deletes only test-generated appointment, doctor, hospital, and user records."""
    yield
    async with AsyncSessionLocal() as session:
        # Delete appointments created for test users or test doctors
        await session.execute(
            delete(Appointment).where(
                or_(
                    Appointment.appointment_token.like("test_appt_%"),
                    Appointment.appointment_token.like("MS-%"),
                )
            )
        )
        # Delete test doctors
        test_doc_users = await session.execute(
            select(User.id).where(User.email.like("test_appt_%"))
        )
        test_user_ids = test_doc_users.scalars().all()
        if test_user_ids:
            await session.execute(delete(Doctor).where(Doctor.user_id.in_(test_user_ids)))
        # Delete test hospitals
        await session.execute(delete(Hospital).where(Hospital.name.like("test_appt_%")))
        # Delete test users
        await session.execute(delete(User).where(User.email.like("test_appt_%")))
        await session.commit()


async def create_test_user(role: str = "patient") -> tuple[uuid.UUID, dict]:
    """Helper to create a temporary test user and return (user_id, auth_headers)."""
    user_id = uuid.uuid4()
    email = f"test_appt_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Test {role.title()} {uuid.uuid4().hex[:4]}",
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role=role)
    return user_id, {"Authorization": f"Bearer {token}"}


async def create_test_doctor_fixture(
    available_days: list[str] = None,
    credential_status: str = "sample",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Creates a temporary doctor linked to a temporary hospital and returns (doctor_id, hospital_id)."""
    if available_days is None:
        available_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    async with AsyncSessionLocal() as session:
        # 1. Hospital
        hosp = Hospital(
            name=f"test_appt_hospital_{uuid.uuid4().hex[:6]}",
            address="Test Medical Street 123",
            city="New Delhi",
            state="Delhi",
            latitude=28.5,
            longitude=77.2,
            is_active=True,
            data_source="sample",
        )
        session.add(hosp)
        await session.flush()

        # 2. Doctor User
        doc_user = User(
            email=f"test_appt_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Dr. Test Specialist {uuid.uuid4().hex[:4]}",
            role="doctor",
            is_active=True,
        )
        session.add(doc_user)
        await session.flush()

        # 3. Doctor Profile
        doctor = Doctor(
            user_id=doc_user.id,
            hospital_id=hosp.id,
            specialty="Cardiology",
            qualification="MBBS, MD (Cardiology)",
            experience_years=12,
            consultation_fee=1000.0,
            is_available=True,
            credential_status=credential_status,
            bio="Test doctor profile for automated integration testing.",
            available_days=available_days,
        )
        session.add(doctor)
        await session.commit()

        return doctor.id, hosp.id


# ==============================================================================
# Doctor Directory & Slots Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_list_doctors_public(client: AsyncClient):
    """Verify public access to /api/v1/doctors without authentication."""
    response = await client.get("/api/v1/doctors")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    first = data["items"][0]
    assert "id" in first
    assert "specialty" in first
    assert "credential_status" in first
    assert "available_days" in first
    assert "user" in first
    assert "hospital" in first


@pytest.mark.asyncio
async def test_filter_doctors_by_specialty_and_credential(client: AsyncClient):
    """Verify multi-facet filtering by specialty and credential status."""
    doc_id, _ = await create_test_doctor_fixture(credential_status="sample")

    res = await client.get("/api/v1/doctors?specialty=Cardiology&credential_status=sample")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(d["id"] == str(doc_id) for d in data["items"])


@pytest.mark.asyncio
async def test_get_doctor_slots_schedule(client: AsyncClient):
    """Verify dynamic slot schedule returns standard 30-min clinic slots."""
    doc_id, _ = await create_test_doctor_fixture()
    future_date = (date.today() + timedelta(days=2)).isoformat()

    res = await client.get(f"/api/v1/doctors/{doc_id}/slots?date={future_date}")
    assert res.status_code == 200
    data = res.json()
    assert data["doctor_id"] == str(doc_id)
    assert data["is_working_day"] is True
    assert len(data["slots"]) >= 10
    # Confirm 13:00 (lunch) is excluded
    slot_times = [s["time"] for s in data["slots"]]
    assert "09:00" in slot_times
    assert "13:00" not in slot_times
    assert "13:30" not in slot_times


@pytest.mark.asyncio
async def test_get_doctor_slots_past_date_rejected(client: AsyncClient):
    """Verify querying slots for past dates returns 400 Bad Request."""
    doc_id, _ = await create_test_doctor_fixture()
    past_date = (date.today() - timedelta(days=1)).isoformat()

    res = await client.get(f"/api/v1/doctors/{doc_id}/slots?date={past_date}")
    assert res.status_code == 400
    assert "past dates" in res.json()["detail"].lower()


# ==============================================================================
# Appointment Booking & Concurrency Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_book_appointment_success(client: AsyncClient):
    """Verify successful booking generates valid token format and returns 201."""
    doc_id, _ = await create_test_doctor_fixture()
    patient_id, headers = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=3)).isoformat()

    payload = {
        "doctor_id": str(doc_id),
        "appointment_date": future_date,
        "appointment_time": "10:00",
        "notes": "Routine blood pressure checkup",
    }

    res = await client.post("/api/v1/appointments", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "appointment_token" in data
    token = data["appointment_token"]
    # Token must match MS-YYYYMMDD-XXXX format
    pattern = r"^MS-\d{8}-[A-F0-9]{4}$"
    assert re.match(pattern, token) is not None, f"Token '{token}' does not match pattern {pattern}"
    assert data["status"] == "scheduled"
    assert data["patient_id"] == str(patient_id)
    assert data["doctor_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_simultaneous_booking_conflict(client: AsyncClient):
    """
    Concurrency Safety Test:
    Two patients attempt to book the exact same slot concurrently.
    PostgreSQL partial unique index 'uq_active_doctor_slot' enforces concurrency safety:
    Exactly one succeeds (201 Created) and the other receives 409 Conflict.
    """
    doc_id, _ = await create_test_doctor_fixture()
    _, headers_patient_a = await create_test_user("patient")
    _, headers_patient_b = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=4)).isoformat()

    payload = {
        "doctor_id": str(doc_id),
        "appointment_date": future_date,
        "appointment_time": "11:30",
        "notes": "Concurrent test booking",
    }

    # Execute concurrent requests
    res_a, res_b = await asyncio.gather(
        client.post("/api/v1/appointments", json=payload, headers=headers_patient_a),
        client.post("/api/v1/appointments", json=payload, headers=headers_patient_b),
    )

    statuses = {res_a.status_code, res_b.status_code}
    assert 201 in statuses, "At least one booking must succeed"
    assert 409 in statuses, "The duplicate booking must be rejected with 409 Conflict by the database partial unique index"

    conflict_res = res_a if res_a.status_code == 409 else res_b
    assert "already booked" in conflict_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_past_date_booking_rejected(client: AsyncClient):
    """Verify backend date boundary validation rejects past dates with 400 Bad Request."""
    doc_id, _ = await create_test_doctor_fixture()
    _, headers = await create_test_user("patient")
    past_date = (date.today() - timedelta(days=1)).isoformat()

    payload = {
        "doctor_id": str(doc_id),
        "appointment_date": past_date,
        "appointment_time": "10:00",
    }
    res = await client.post("/api/v1/appointments", json=payload, headers=headers)
    assert res.status_code == 400
    assert "past date" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_slot_time_boundary_rejected(client: AsyncClient):
    """Verify backend boundary validation rejects non-conforming slot times with 400 Bad Request."""
    doc_id, _ = await create_test_doctor_fixture()
    _, headers = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=2)).isoformat()

    # Irregular non-half-hour time (10:17)
    payload_irregular = {
        "doctor_id": str(doc_id),
        "appointment_date": future_date,
        "appointment_time": "10:17",
    }
    res1 = await client.post("/api/v1/appointments", json=payload_irregular, headers=headers)
    assert res1.status_code == 400
    assert "30-minute clinic slot" in res1.json()["detail"]

    # Lunch hour (13:00)
    payload_lunch = {
        "doctor_id": str(doc_id),
        "appointment_date": future_date,
        "appointment_time": "13:00",
    }
    res2 = await client.post("/api/v1/appointments", json=payload_lunch, headers=headers)
    assert res2.status_code == 400
    assert "30-minute clinic slot" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_doctor_unavailable_day_rejected(client: AsyncClient):
    """Verify backend schedule check rejects booking on doctor's off-day with 400 Bad Request."""
    # Doctor only works on Mondays
    doc_id, _ = await create_test_doctor_fixture(available_days=["Monday"])
    _, headers = await create_test_user("patient")

    # Find next Tuesday
    today = date.today()
    days_until_tuesday = (1 - today.weekday() + 7) % 7
    if days_until_tuesday == 0:
        days_until_tuesday = 7
    tuesday_date = (today + timedelta(days=days_until_tuesday)).isoformat()

    payload = {
        "doctor_id": str(doc_id),
        "appointment_date": tuesday_date,
        "appointment_time": "09:30",
    }
    res = await client.post("/api/v1/appointments", json=payload, headers=headers)
    assert res.status_code == 400
    assert "does not take consultations on tuesday" in res.json()["detail"].lower()


# ==============================================================================
# Patient Data Isolation & Authorization Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_patient_can_only_view_own_appointments(client: AsyncClient):
    """Verify cross-patient snooping on GET /api/v1/appointments/{id} returns 403 Forbidden."""
    doc_id, _ = await create_test_doctor_fixture()
    _, headers_patient_a = await create_test_user("patient")
    _, headers_patient_b = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=3)).isoformat()

    # Patient A books
    res_book = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": "14:00"},
        headers=headers_patient_a,
    )
    assert res_book.status_code == 201
    appt_id = res_book.json()["id"]

    # Patient A can view it
    res_view_a = await client.get(f"/api/v1/appointments/{appt_id}", headers=headers_patient_a)
    assert res_view_a.status_code == 200

    # Patient B cannot view Patient A's appointment (403 Forbidden)
    res_view_b = await client.get(f"/api/v1/appointments/{appt_id}", headers=headers_patient_b)
    assert res_view_b.status_code == 403
    assert "access denied" in res_view_b.json()["detail"].lower()


@pytest.mark.asyncio
async def test_patient_cannot_cancel_others_appointment(client: AsyncClient):
    """Verify cross-patient cancellation attempt returns 403 Forbidden."""
    doc_id, _ = await create_test_doctor_fixture()
    _, headers_patient_a = await create_test_user("patient")
    _, headers_patient_b = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=3)).isoformat()

    # Patient A books
    res_book = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": "15:00"},
        headers=headers_patient_a,
    )
    appt_id = res_book.json()["id"]

    # Patient B attempts to cancel Patient A's appointment
    res_cancel_b = await client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"cancellation_reason": "Malicious attempt"},
        headers=headers_patient_b,
    )
    assert res_cancel_b.status_code == 403
    assert "access denied" in res_cancel_b.json()["detail"].lower()


# ==============================================================================
# Cancellation & Partial Unique Index Slot Freeing Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_cancel_appointment_frees_slot_for_rebooking(client: AsyncClient):
    """
    Verify cancellation updates status to 'cancelled' and immediately frees the slot
    in PostgreSQL's partial unique index so another patient can book it without conflict.
    """
    doc_id, _ = await create_test_doctor_fixture()
    _, headers_patient_a = await create_test_user("patient")
    _, headers_patient_b = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=5)).isoformat()
    slot_time = "16:00"

    # 1. Patient A books slot
    res1 = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": slot_time},
        headers=headers_patient_a,
    )
    assert res1.status_code == 201
    appt_id = res1.json()["id"]

    # 2. Patient B tries to book the same slot -> 409 Conflict
    res_conflict = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": slot_time},
        headers=headers_patient_b,
    )
    assert res_conflict.status_code == 409

    # 3. Patient A cancels the appointment
    res_cancel = await client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"cancellation_reason": "Schedule conflict"},
        headers=headers_patient_a,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # 4. Patient B now books the EXACT SAME slot -> Succeeds with 201 Created!
    res_rebook = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": slot_time},
        headers=headers_patient_b,
    )
    assert res_rebook.status_code == 201
    assert res_rebook.json()["status"] == "scheduled"
    assert res_rebook.json()["appointment_time"] == "16:00:00"


@pytest.mark.asyncio
async def test_re_cancelling_already_cancelled_appointment_rejected(client: AsyncClient):
    """Verify cannot cancel an appointment that is already cancelled (returns 400)."""
    doc_id, _ = await create_test_doctor_fixture()
    _, headers = await create_test_user("patient")
    future_date = (date.today() + timedelta(days=3)).isoformat()

    res_book = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id), "appointment_date": future_date, "appointment_time": "09:00"},
        headers=headers,
    )
    appt_id = res_book.json()["id"]

    # First cancel
    res_c1 = await client.post(f"/api/v1/appointments/{appt_id}/cancel", headers=headers)
    assert res_c1.status_code == 200

    # Second cancel attempt on already cancelled appointment
    res_c2 = await client.post(f"/api/v1/appointments/{appt_id}/cancel", headers=headers)
    assert res_c2.status_code == 400
    assert "already cancelled" in res_c2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_uniqueness_enforced_in_postgresql():
    """Verify that PostgreSQL rejects duplicate appointment tokens at database level."""
    doc_id, hosp_id = await create_test_doctor_fixture()
    patient_id, _ = await create_test_user("patient")
    duplicate_token = f"MS-{date.today().strftime('%Y%m%d')}-DUPL"

    async with AsyncSessionLocal() as session:
        appt1 = Appointment(
            appointment_token=duplicate_token,
            patient_id=patient_id,
            doctor_id=doc_id,
            hospital_id=hosp_id,
            appointment_date=date.today() + timedelta(days=6),
            appointment_time=time(9, 0),
            status="scheduled",
        )
        session.add(appt1)
        await session.commit()

    # Attempt inserting second appointment with identical token
    with pytest.raises(IntegrityError):
        async with AsyncSessionLocal() as session:
            appt2 = Appointment(
                appointment_token=duplicate_token,
                patient_id=patient_id,
                doctor_id=doc_id,
                hospital_id=hosp_id,
                appointment_date=date.today() + timedelta(days=7),
                appointment_time=time(10, 0),
                status="scheduled",
            )
            session.add(appt2)
            await session.commit()
