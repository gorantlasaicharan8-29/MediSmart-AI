import uuid
from datetime import date, datetime, time, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_queue_prediction_test_data():
    """Non-destructive fixture: deletes only test-generated records."""
    yield
    async with AsyncSessionLocal() as session:
        # Delete test queue entries
        await session.execute(
            delete(QueueEntry).where(QueueEntry.notes.like("test_iqp_%"))
        )
        # Delete test appointments
        await session.execute(
            delete(Appointment).where(
                or_(
                    Appointment.appointment_token.like("test_iqp_%"),
                    Appointment.appointment_token.like("MS-%"),
                )
            )
        )
        # Delete test doctors
        test_doc_users = await session.execute(
            select(User.id).where(User.email.like("test_iqp_%"))
        )
        test_user_ids = test_doc_users.scalars().all()
        if test_user_ids:
            await session.execute(delete(Doctor).where(Doctor.user_id.in_(test_user_ids)))
        # Delete test hospitals
        await session.execute(delete(Hospital).where(Hospital.name.like("test_iqp_%")))
        # Delete test users
        await session.execute(delete(User).where(User.email.like("test_iqp_%")))
        await session.commit()


async def create_iqp_test_user(role: str = "patient") -> tuple[uuid.UUID, dict]:
    """Helper to create an active test user and return (user_id, headers)."""
    user_id = uuid.uuid4()
    email = f"test_iqp_{role}_{uuid.uuid4().hex[:6]}@example.com"
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


async def create_iqp_doctor_fixture(specialty: str = "Cardiology") -> tuple[Doctor, Hospital, User]:
    """Creates a temporary doctor linked to a temporary hospital."""
    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            name=f"test_iqp_hospital_{uuid.uuid4().hex[:6]}",
            address="Test Clinic Blvd",
            city="Hyderabad",
            state="Telangana",
            is_active=True,
            data_source="verified",
        )
        session.add(hosp)
        await session.flush()

        doc_user = User(
            email=f"test_iqp_doc_{uuid.uuid4().hex[:6]}@example.com",
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
            specialty=specialty,
            qualification="MBBS, MD",
            experience_years=14,
            consultation_fee=1200.0,
            is_available=True,
            credential_status="verified",
            available_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        )
        session.add(doctor)
        await session.commit()

        # Reload with user and hospital
        res = await session.execute(
            select(Doctor)
            .where(Doctor.id == doctor.id)
            .options(selectinload(Doctor.user), selectinload(Doctor.hospital))
        )
        return res.scalar_one(), hosp, doc_user


# ==============================================================================
# Patient Queue Prediction Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_patient_queue_prediction_success(client: AsyncClient):
    """
    Authenticated patient with an active queue entry can retrieve their intelligent
    real-time prediction with model metadata and explainability.
    """
    patient_id, patient_headers = await create_iqp_test_user("patient")
    doctor, hospital, _ = await create_iqp_doctor_fixture("Cardiology")
    today = date.today()

    async with AsyncSessionLocal() as session:
        # Create appointment and queue entry
        appt = Appointment(
            patient_id=patient_id,
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            appointment_date=today,
            appointment_time=time(10, 30),
            status="checked_in",
            appointment_token="test_iqp_token_01",
        )
        session.add(appt)
        await session.flush()

        q_entry = QueueEntry(
            id=uuid.uuid4(),
            appointment_id=appt.id,
            hospital_id=hospital.id,
            doctor_id=doctor.id,
            patient_id=patient_id,
            queue_date=today,
            token_number=1,
            position=1,
            status="waiting",
            notes="test_iqp_patient",
            checked_in_at=datetime.now(timezone.utc),
        )
        session.add(q_entry)
        await session.commit()

    res = await client.get("/api/v1/predictions/queue/my", headers=patient_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["token_number"] == 1
    assert data["position"] == 1
    assert data["patients_ahead"] == 0
    assert data["queue_status"] == "waiting"
    assert data["doctor_specialty"] == "Cardiology"
    assert data["model_name"] in ["xgboost", "next_in_line"]
    assert "explanation" in data
    assert "Your estimated waiting time" in data["explanation"]


@pytest.mark.asyncio
async def test_patient_isolation_when_no_active_entry(client: AsyncClient):
    """
    A patient with no active queue entry today receives HTTP 404
    and cannot see any other patient's queue details.
    """
    _, patient_headers = await create_iqp_test_user("patient")
    res = await client.get("/api/v1/predictions/queue/my", headers=patient_headers)
    assert res.status_code == 404
    assert "No active queue entry found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_patient_forbidden_from_doctor_queue_analytics(client: AsyncClient):
    """
    Patients cannot access doctor-level queue analytics (HTTP 403 Forbidden).
    """
    _, patient_headers = await create_iqp_test_user("patient")
    res = await client.get("/api/v1/predictions/doctor/queue-analytics", headers=patient_headers)
    assert res.status_code == 403


# ==============================================================================
# Doctor Queue Analytics Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_doctor_queue_analytics_success(client: AsyncClient):
    """
    Doctor can access their live queue analytics including congestion status and clearing time.
    """
    doctor, hospital, doc_user = await create_iqp_doctor_fixture("Neurology")
    doc_token = create_access_token(user_id=doc_user.id, role="doctor")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    today = date.today()

    patient_id, _ = await create_iqp_test_user("patient")

    async with AsyncSessionLocal() as session:
        # Add 2 waiting patients
        for i in range(1, 3):
            appt = Appointment(
                patient_id=patient_id,
                doctor_id=doctor.id,
                hospital_id=hospital.id,
                appointment_date=today,
                appointment_time=time(10 + i, 0),
                status="checked_in",
                appointment_token=f"test_iqp_appt_{i}",
            )
            session.add(appt)
            await session.flush()

            q_entry = QueueEntry(
                id=uuid.uuid4(),
                appointment_id=appt.id,
                hospital_id=hospital.id,
                doctor_id=doctor.id,
                patient_id=patient_id,
                queue_date=today,
                token_number=i,
                position=i,
                status="waiting",
                notes="test_iqp_waiting",
                checked_in_at=datetime.now(timezone.utc),
            )
            session.add(q_entry)
        await session.commit()

    res = await client.get("/api/v1/predictions/doctor/queue-analytics", headers=doc_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["doctor_id"] == str(doctor.id)
    assert data["waiting_patients_count"] == 2
    assert data["queue_congestion_status"] in ["low", "moderate"]
    assert len(data["waiting_queue"]) == 2
    assert data["estimated_clearing_time_minutes"] > 0
    assert "analytics_summary" in data


@pytest.mark.asyncio
async def test_active_consultation_elapsed_time_handling(client: AsyncClient):
    """
    When a doctor has an active consultation in progress, the elapsed time
    is measured and incorporated into predictions for the waiting queue.
    """
    doctor, hospital, doc_user = await create_iqp_doctor_fixture("Cardiology")
    today = date.today()

    patient1_id, _ = await create_iqp_test_user("patient")
    patient2_id, patient2_headers = await create_iqp_test_user("patient")

    # Start Patient 1 consultation 10 minutes ago
    called_at_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    async with AsyncSessionLocal() as session:
        # Patient 1: in_consultation
        appt1 = Appointment(
            patient_id=patient1_id,
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            appointment_date=today,
            appointment_time=time(9, 30),
            status="in_progress",
            appointment_token="test_iqp_active_01",
        )
        session.add(appt1)
        await session.flush()

        q1 = QueueEntry(
            id=uuid.uuid4(),
            appointment_id=appt1.id,
            hospital_id=hospital.id,
            doctor_id=doctor.id,
            patient_id=patient1_id,
            queue_date=today,
            token_number=1,
            position=0,
            status="in_consultation",
            notes="test_iqp_active",
            checked_in_at=called_at_time - timedelta(minutes=15),
            called_at=called_at_time,
        )
        session.add(q1)

        # Patient 2: waiting (next in line)
        appt2 = Appointment(
            patient_id=patient2_id,
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            appointment_date=today,
            appointment_time=time(10, 0),
            status="checked_in",
            appointment_token="test_iqp_waiting_02",
        )
        session.add(appt2)
        await session.flush()

        q2 = QueueEntry(
            id=uuid.uuid4(),
            appointment_id=appt2.id,
            hospital_id=hospital.id,
            doctor_id=doctor.id,
            patient_id=patient2_id,
            queue_date=today,
            token_number=2,
            position=1,
            status="waiting",
            notes="test_iqp_waiting",
            checked_in_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        session.add(q2)
        await session.commit()

    # Query prediction for Patient 2
    res = await client.get("/api/v1/predictions/queue/my", headers=patient2_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["is_doctor_active_consultation"] is True
    assert data["current_consultation_elapsed_minutes"] is not None
    assert data["current_consultation_elapsed_minutes"] >= 9.0  # Approx 10 minutes elapsed
    assert data["estimated_wait_minutes"] >= 1  # Patient must wait for active consultation to conclude


@pytest.mark.asyncio
async def test_public_waiting_room_monitor_zero_pii(client: AsyncClient):
    """
    Public waiting room board displays predicted waiting minutes without exposing any patient PII.
    """
    doctor, hospital, _ = await create_iqp_doctor_fixture("Pediatrics")
    today = date.today()
    patient_id, _ = await create_iqp_test_user("patient")

    async with AsyncSessionLocal() as session:
        appt = Appointment(
            patient_id=patient_id,
            doctor_id=doctor.id,
            hospital_id=hospital.id,
            appointment_date=today,
            appointment_time=time(14, 0),
            status="checked_in",
            appointment_token="test_iqp_public_tok",
        )
        session.add(appt)
        await session.flush()

        q = QueueEntry(
            id=uuid.uuid4(),
            appointment_id=appt.id,
            hospital_id=hospital.id,
            doctor_id=doctor.id,
            patient_id=patient_id,
            queue_date=today,
            token_number=1,
            position=1,
            status="waiting",
            notes="test_iqp_public",
            checked_in_at=datetime.now(timezone.utc),
        )
        session.add(q)
        await session.commit()

    res = await client.get(f"/api/v1/queue/doctor/{doctor.id}/public-board")
    assert res.status_code == 200
    data = res.json()

    assert "waiting_list" in data
    assert len(data["waiting_list"]) == 1
    item = data["waiting_list"][0]

    # Verify predictions present
    assert "estimated_wait_minutes" in item
    assert "token_display" in item

    # Verify zero PII
    item_str = str(item)
    assert "email" not in item_str
    assert "phone" not in item_str
    assert "patient_name" not in item_str
    assert "notes" not in item_str
