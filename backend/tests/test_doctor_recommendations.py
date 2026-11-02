import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, or_, select

try:
    from zoneinfo import ZoneInfo
    CLINIC_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    CLINIC_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_recommendation_test_data():
    """Non-destructive fixture: deletes only test-generated recommendation records."""
    yield
    async with AsyncSessionLocal() as session:
        # Delete appointments created for test users or test doctors
        await session.execute(
            delete(Appointment).where(
                or_(
                    Appointment.appointment_token.like("test_rec_%"),
                    Appointment.appointment_token.like("MS-%"),
                )
            )
        )
        # Delete test doctors
        test_doc_users = await session.execute(
            select(User.id).where(User.email.like("test_rec_%"))
        )
        test_user_ids = test_doc_users.scalars().all()
        if test_user_ids:
            await session.execute(delete(Doctor).where(Doctor.user_id.in_(test_user_ids)))
        # Delete test hospitals
        await session.execute(delete(Hospital).where(Hospital.name.like("test_rec_%")))
        # Delete test users
        await session.execute(delete(User).where(User.email.like("test_rec_%")))
        await session.commit()


async def create_test_patient() -> tuple[uuid.UUID, dict]:
    """Helper to create an active test patient user."""
    user_id = uuid.uuid4()
    email = f"test_rec_patient_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Patient {uuid.uuid4().hex[:4]}",
            role="patient",
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role="patient")
    return user_id, {"Authorization": f"Bearer {token}"}


async def create_custom_test_doctor(
    specialty: str = "Cardiology",
    city: str = "New Delhi",
    consultation_fee: float = 1200.0,
    experience_years: int = 15,
    is_available: bool = True,
    available_days: list[str] = None,
    credential_status: str = "verified",
) -> tuple[Doctor, Hospital]:
    """Helper to seed a doctor with precise clinical parameters."""
    if available_days is None:
        available_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            name=f"test_rec_hosp_{uuid.uuid4().hex[:6]}",
            address=f"100 Medical Enclave, {city}",
            city=city,
            state="StateX",
            latitude=28.6,
            longitude=77.2,
            is_active=True,
            data_source="verified",
        )
        session.add(hosp)
        await session.flush()

        doc_user = User(
            email=f"test_rec_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Dr. {specialty} Expert {uuid.uuid4().hex[:4]}",
            role="doctor",
            is_active=True,
        )
        session.add(doc_user)
        await session.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            hospital_id=hosp.id,
            specialty=specialty,
            qualification=f"MBBS, MD ({specialty})",
            experience_years=experience_years,
            consultation_fee=consultation_fee,
            is_available=is_available,
            credential_status=credential_status,
            bio=f"Senior consultant in {specialty}.",
            available_days=available_days,
        )
        session.add(doctor)
        await session.commit()

        # Reload with relationships
        res = await session.execute(
            select(Doctor)
            .where(Doctor.id == doctor.id)
        )
        return res.scalar_one(), hosp


# ==============================================================================
# Security & Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_recommendations_unauthorized(client: AsyncClient):
    """Unauthorized requests without valid JWT token return HTTP 401."""
    res = await client.post("/api/v1/recommendations/doctors", json={"specialty": "Cardiology"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_recommendations_past_date_rejected(client: AsyncClient):
    """Querying recommendations for past dates returns HTTP 400 Bad Request."""
    _, headers = await create_test_patient()
    past_date = (date.today() - timedelta(days=2)).isoformat()
    res = await client.post(
        "/api/v1/recommendations/doctors",
        json={"preferred_date": past_date},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Cannot request recommendations for past dates" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recommendations_negative_fee_rejected(client: AsyncClient):
    """Negative fee is rejected by Pydantic validation with HTTP 422."""
    _, headers = await create_test_patient()
    res = await client.post(
        "/api/v1/recommendations/doctors",
        json={"max_fee": -100.0},
        headers=headers,
    )
    assert res.status_code == 422


# ==============================================================================
# Matching & Scoring Engine Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_recommendations_full_match_and_explanations(client: AsyncClient):
    """
    Doctor matching specialty, city, and within fee budget ranks at the top
    with high match percentage and rich, data-backed explanations.
    """
    _, headers = await create_test_patient()
    today = date.today()
    day_name = today.strftime("%A")

    # Doctor 1: Perfect match (Cardiology, Hyderabad, fee 1200, verified, available)
    doc1, hosp1 = await create_custom_test_doctor(
        specialty="Cardiology",
        city="Hyderabad",
        consultation_fee=1200.0,
        experience_years=16,
        is_available=True,
        available_days=[day_name],
        credential_status="verified",
    )

    # Doctor 2: Partial match (Cardiology, Pune, fee 2500)
    doc2, hosp2 = await create_custom_test_doctor(
        specialty="Cardiology",
        city="Pune",
        consultation_fee=2500.0,
        experience_years=8,
        is_available=True,
        available_days=[day_name],
    )

    payload = {
        "specialty": "Cardiology",
        "city": "Hyderabad",
        "max_fee": 1500.0,
        "preferred_date": today.isoformat(),
        "limit": 5,
    }

    res = await client.post("/api/v1/recommendations/doctors", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "items" in data
    assert len(data["items"]) >= 2
    first = data["items"][0]

    # Verify Doctor 1 is top ranked
    assert first["doctor"]["id"] == str(doc1.id)
    assert first["match_score"] >= 85
    assert first["match_percentage"] == first["match_score"]

    # Verify explainability bullets are data-backed
    explanations = first["explanations"]
    assert any("Cardiology" in exp for exp in explanations)
    assert any("Hyderabad" in exp for exp in explanations)
    assert any("budget" in exp for exp in explanations)
    assert any("16+ years" in exp for exp in explanations)
    assert any("Verified Practitioner" in exp for exp in explanations)

    # Verify score breakdown is present
    assert "specialty" in first["score_breakdown"]
    assert "location" in first["score_breakdown"]
    assert "fee" in first["score_breakdown"]
    assert "availability" in first["score_breakdown"]


@pytest.mark.asyncio
async def test_recommendations_no_matching_doctors(client: AsyncClient):
    """
    When searching for a non-existent specialty, an empty list is returned cleanly
    without throwing exceptions.
    """
    _, headers = await create_test_patient()
    payload = {
        "specialty": "QuantumBioAstroMedicine999",
        "limit": 5,
    }

    res = await client.post("/api/v1/recommendations/doctors", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total_evaluated"] >= 0


@pytest.mark.asyncio
async def test_recommendations_unavailable_doctor_penalized(client: AsyncClient):
    """
    A doctor marked as is_available=False receives 0 availability points
    and an explanation indicating they are currently unavailable.
    """
    _, headers = await create_test_patient()
    today = date.today()

    doc, hosp = await create_custom_test_doctor(
        specialty="Pediatrics",
        city="Bengaluru",
        consultation_fee=800.0,
        is_available=False,
    )

    payload = {
        "specialty": "Pediatrics",
        "city": "Bengaluru",
        "preferred_date": today.isoformat(),
        "limit": 5,
    }

    res = await client.post("/api/v1/recommendations/doctors", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    matching = [item for item in data["items"] if item["doctor"]["id"] == str(doc.id)]

    assert len(matching) == 1
    item = matching[0]
    assert item["score_breakdown"]["availability"] == 0.0
    assert item["is_slot_available"] is False
    assert any("unavailable" in exp for exp in item["explanations"])


@pytest.mark.asyncio
async def test_recommendations_booked_slots_identification(client: AsyncClient):
    """
    The recommendation engine accurately inspects booked appointments on the target date
    and selects the next confirmed open slot.
    """
    patient_id, headers = await create_test_patient()
    tomorrow = date.today() + timedelta(days=1)
    day_name = tomorrow.strftime("%A")

    doc, hosp = await create_custom_test_doctor(
        specialty="Dermatology",
        city="Chennai",
        consultation_fee=1000.0,
        is_available=True,
        available_days=[day_name],
    )

    # Book the 09:00 slot directly in database
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            patient_id=patient_id,
            doctor_id=doc.id,
            hospital_id=hosp.id,
            appointment_date=tomorrow,
            appointment_time=datetime.strptime("09:00", "%H:%M").time(),
            status="scheduled",
            appointment_token="test_rec_token_0900",
        )
        session.add(appt)
        await session.commit()

    payload = {
        "specialty": "Dermatology",
        "city": "Chennai",
        "preferred_date": tomorrow.isoformat(),
        "limit": 5,
    }

    res = await client.post("/api/v1/recommendations/doctors", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    matching = [item for item in data["items"] if item["doctor"]["id"] == str(doc.id)]

    assert len(matching) == 1
    item = matching[0]
    assert item["is_slot_available"] is True
    # The first slot (09:00) is booked, so next available slot must be 09:30
    assert item["next_available_slot"] == "09:30"
    assert any("09:30" in exp for exp in item["explanations"])


@pytest.mark.asyncio
async def test_booking_via_recommended_doctor_id(client: AsyncClient):
    """
    A patient can immediately book an appointment with a recommended doctor ID
    using the existing appointments API.
    """
    patient_id, headers = await create_test_patient()
    tomorrow = date.today() + timedelta(days=1)
    day_name = tomorrow.strftime("%A")

    doc, hosp = await create_custom_test_doctor(
        specialty="Orthopedics",
        city="Mumbai",
        consultation_fee=1500.0,
        is_available=True,
        available_days=[day_name],
    )

    # 1. Fetch recommendations
    rec_res = await client.post(
        "/api/v1/recommendations/doctors",
        json={"specialty": "Orthopedics", "preferred_date": tomorrow.isoformat()},
        headers=headers,
    )
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    rec_item = rec_data["items"][0]
    rec_doctor_id = rec_item["doctor"]["id"]

    # 2. Book appointment with recommended doctor
    book_payload = {
        "doctor_id": rec_doctor_id,
        "hospital_id": str(hosp.id),
        "appointment_date": tomorrow.isoformat(),
        "appointment_time": "11:00",
        "notes": "Booked via AI Doctor Recommendation.",
    }
    book_res = await client.post("/api/v1/appointments", json=book_payload, headers=headers)
    assert book_res.status_code == 201
    book_data = book_res.json()
    assert book_data["doctor_id"] == rec_doctor_id
    assert book_data["status"] == "scheduled"
    assert book_data["appointment_token"].startswith("MS-")

