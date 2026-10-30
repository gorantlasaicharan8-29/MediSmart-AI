import uuid
from datetime import date, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User
from tests.test_appointments import create_test_doctor_fixture, create_test_user


@pytest.mark.asyncio
async def test_get_my_doctor_profile_success(client: AsyncClient):
    """Doctor can fetch their own profile via /api/v1/doctors/me."""
    doc_id, hosp_id = await create_test_doctor_fixture()

    # Find doctor's user
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Doctor).where(Doctor.id == doc_id))
        doc = res.scalar_one()
        user_id = doc.user_id

    # Create auth headers for doctor user
    from app.core.security import create_access_token
    token = create_access_token(user_id=user_id, role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/v1/doctors/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(doc_id)
    assert data["user_id"] == str(user_id)
    assert "user" in data
    assert "hospital" in data


@pytest.mark.asyncio
async def test_get_my_doctor_profile_forbidden_for_patient(client: AsyncClient):
    """Patients cannot access /api/v1/doctors/me."""
    patient_id, headers = await create_test_user("patient")
    res = await client.get("/api/v1/doctors/me", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_my_doctor_profile(client: AsyncClient):
    """Doctor can safely update their bio, availability, and consultation fee."""
    doc_id, hosp_id = await create_test_doctor_fixture()

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Doctor).where(Doctor.id == doc_id))
        doc = res.scalar_one()
        user_id = doc.user_id

    from app.core.security import create_access_token
    token = create_access_token(user_id=user_id, role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "bio": "Senior specialist with extensive clinical background.",
        "is_available": True,
        "available_days": ["Monday", "Wednesday", "Friday"],
        "consultation_fee": 1500.0,
    }

    res = await client.patch("/api/v1/doctors/me", json=update_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["bio"] == update_payload["bio"]
    assert data["consultation_fee"] == 1500.0
    assert data["available_days"] == ["Monday", "Wednesday", "Friday"]


@pytest.mark.asyncio
async def test_get_my_doctor_stats(client: AsyncClient):
    """Doctor can fetch dashboard summary stats."""
    doc_id, hosp_id = await create_test_doctor_fixture()

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Doctor).where(Doctor.id == doc_id))
        doc = res.scalar_one()
        user_id = doc.user_id

    from app.core.security import create_access_token
    token = create_access_token(user_id=user_id, role="doctor")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/v1/doctors/me/stats", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "today_appointments" in data
    assert "waiting_patients" in data
    assert "completed_consultations" in data
    assert "queue_date" in data
    assert data["doctor_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_list_appointments_with_date_filter(client: AsyncClient):
    """Verify that appointments can be filtered by date."""
    doc_id, hosp_id = await create_test_doctor_fixture()
    patient_id, pat_headers = await create_test_user("patient")

    target_date = (date.today() + timedelta(days=4)).isoformat()
    payload = {
        "doctor_id": str(doc_id),
        "appointment_date": target_date,
        "appointment_time": "10:00",
        "notes": "Testing date filter",
    }
    b_res = await client.post("/api/v1/appointments", json=payload, headers=pat_headers)
    assert b_res.status_code == 201

    # Filter with matching date
    res = await client.get(f"/api/v1/appointments?date={target_date}", headers=pat_headers)
    assert res.status_code == 200
    data = res.json()
    assert any(a["appointment_date"] == target_date for a in data["items"])

    # Filter with non-matching date
    other_date = (date.today() + timedelta(days=10)).isoformat()
    res_other = await client.get(f"/api/v1/appointments?date={other_date}", headers=pat_headers)
    assert res_other.status_code == 200
    assert len(res_other.json()["items"]) == 0
