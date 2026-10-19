"""
Tests for Phase 5.1 Queue Models, Unique Constraints, and Concurrency Controls.
"""
import asyncio
import uuid
from datetime import date, datetime, time, timezone
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User


@pytest.fixture
async def db_session():
    """Provides a transactional database session for tests with automatic rollback."""
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_doctor_and_hospital(db_session):
    """Retrieve an existing doctor and hospital from the seeded database."""
    res_hosp = await db_session.execute(text("SELECT id FROM hospitals LIMIT 1;"))
    hosp_id = res_hosp.scalar()

    res_doc = await db_session.execute(
        text("SELECT id, user_id FROM doctors WHERE hospital_id = :hid LIMIT 1;"),
        {"hid": hosp_id},
    )
    doc_row = res_doc.fetchone()
    assert hosp_id is not None, "No seeded hospital found"
    assert doc_row is not None, "No seeded doctor found"
    doc_id, doc_user_id = doc_row[0], doc_row[1]

    # Find a patient user (different from doctor user)
    res_patient = await db_session.execute(
        text("SELECT id FROM users WHERE id != :doc_uid LIMIT 1;"),
        {"doc_uid": doc_user_id},
    )
    patient_id = res_patient.scalar()
    assert patient_id is not None, "No patient user found"

    return {
        "hospital_id": hosp_id,
        "doctor_id": doc_id,
        "patient_id": patient_id,
    }


@pytest.mark.asyncio
async def test_token_display_computed_property():
    """Verify that token_display is computed dynamically without requiring a redundant DB column."""
    entry = QueueEntry(
        token_number=1,
        position=1,
        status="waiting",
        queue_date=date.today(),
    )
    assert entry.token_display == "Q-001"

    entry.token_number = 42
    assert entry.token_display == "Q-042"

    entry.token_number = 105
    assert entry.token_display == "Q-105"


@pytest.mark.asyncio
async def test_prevent_duplicate_appointment_check_in(db_session, test_doctor_and_hospital):
    """Verify that the preserved unique constraint queue_entries_appointment_id_key prevents duplicate check-in."""
    data = test_doctor_and_hospital
    test_date = date(2027, 1, 1)

    # Create a test appointment
    appt_token = f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    appt = Appointment(
        appointment_token=appt_token,
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        hospital_id=data["hospital_id"],
        appointment_date=test_date,
        appointment_time=time(10, 0),
        status="scheduled",
    )
    db_session.add(appt)
    await db_session.flush()

    # Create first queue entry
    entry1 = QueueEntry(
        appointment_id=appt.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=1,
        position=1,
        status="waiting",
    )
    db_session.add(entry1)
    await db_session.flush()

    # Attempt to create duplicate queue entry for the same appointment
    entry2 = QueueEntry(
        appointment_id=appt.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=2,
        position=2,
        status="waiting",
    )
    db_session.add(entry2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()

    assert "queue_entries_appointment_id_key" in str(exc_info.value) or "unique" in str(exc_info.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_unique_active_consultation_per_doctor_per_date(db_session, test_doctor_and_hospital):
    """Verify that partial index uq_active_doctor_in_consultation restricts doctor to at most one active consultation per clinic date."""
    data = test_doctor_and_hospital
    test_date = date(2027, 1, 2)

    # Create two appointments
    appt1 = Appointment(
        appointment_token=f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        hospital_id=data["hospital_id"],
        appointment_date=test_date,
        appointment_time=time(10, 0),
        status="in_progress",
    )
    appt2 = Appointment(
        appointment_token=f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        hospital_id=data["hospital_id"],
        appointment_date=test_date,
        appointment_time=time(10, 30),
        status="in_progress",
    )
    db_session.add_all([appt1, appt2])
    await db_session.flush()

    # First patient in consultation
    entry1 = QueueEntry(
        appointment_id=appt1.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=1,
        position=1,
        status="in_consultation",
        called_at=datetime.now(timezone.utc),
    )
    db_session.add(entry1)
    await db_session.flush()

    # Second patient also marked in_consultation for same doctor and same clinic date -> Must fail!
    entry2 = QueueEntry(
        appointment_id=appt2.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=2,
        position=2,
        status="in_consultation",
        called_at=datetime.now(timezone.utc),
    )
    db_session.add(entry2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()

    assert "uq_active_doctor_in_consultation" in str(exc_info.value) or "unique" in str(exc_info.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_unique_token_number_per_doctor_per_date(db_session, test_doctor_and_hospital):
    """Verify that unique constraint uq_doctor_date_token_number prevents duplicate tokens for a doctor on a clinic date."""
    data = test_doctor_and_hospital
    test_date = date(2027, 1, 3)

    appt1 = Appointment(
        appointment_token=f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        hospital_id=data["hospital_id"],
        appointment_date=test_date,
        appointment_time=time(9, 0),
        status="scheduled",
    )
    appt2 = Appointment(
        appointment_token=f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
        patient_id=data["patient_id"],
        doctor_id=data["doctor_id"],
        hospital_id=data["hospital_id"],
        appointment_date=test_date,
        appointment_time=time(9, 30),
        status="scheduled",
    )
    db_session.add_all([appt1, appt2])
    await db_session.flush()

    entry1 = QueueEntry(
        appointment_id=appt1.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=1,
        position=1,
        status="waiting",
    )
    db_session.add(entry1)
    await db_session.flush()

    # Attempting to insert token_number=1 again for the same doctor and same queue_date
    entry2 = QueueEntry(
        appointment_id=appt2.id,
        hospital_id=data["hospital_id"],
        doctor_id=data["doctor_id"],
        patient_id=data["patient_id"],
        queue_date=test_date,
        token_number=1,  # DUPLICATE TOKEN
        position=2,
        status="waiting",
    )
    db_session.add(entry2)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.flush()

    assert "uq_doctor_date_token_number" in str(exc_info.value) or "unique" in str(exc_info.value).lower()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_concurrent_token_allocation_with_advisory_lock(test_doctor_and_hospital):
    """
    Simulation test for concurrent token allocation using PostgreSQL advisory lock.
    Verifies the database transaction-scoped lock and sequence generation pattern.
    NOTE: As per user specifications, full end-to-end API verification of this flow
    will be conducted in Plan 5.2 upon endpoint implementation.
    """
    data = test_doctor_and_hospital
    test_date = date(2027, 1, 4)

    async def check_in_patient(patient_idx: int) -> int:
        async with AsyncSessionLocal() as session:
            # 1. Acquire transaction-scoped advisory lock for the doctor on this clinic date
            lock_key = f"queue_token_{data['doctor_id']}_{test_date}"
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key));"),
                {"lock_key": lock_key},
            )

            # 2. Create appointment with non-colliding slot
            appt = Appointment(
                appointment_token=f"MS-{test_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                patient_id=data["patient_id"],
                doctor_id=data["doctor_id"],
                hospital_id=data["hospital_id"],
                appointment_date=test_date,
                appointment_time=time(14, patient_idx * 10),
                status="scheduled",
            )
            session.add(appt)
            await session.flush()

            # 3. Calculate next sequential token
            res = await session.execute(
                text("""
                    SELECT COALESCE(MAX(token_number), 0) + 1 
                    FROM queue_entries 
                    WHERE doctor_id = :doc_id AND queue_date = :qdate;
                """),
                {"doc_id": data["doctor_id"], "qdate": test_date},
            )
            next_token = res.scalar()

            # 4. Insert queue entry
            entry = QueueEntry(
                appointment_id=appt.id,
                hospital_id=data["hospital_id"],
                doctor_id=data["doctor_id"],
                patient_id=data["patient_id"],
                queue_date=test_date,
                token_number=next_token,
                position=next_token,
                status="waiting",
            )
            session.add(entry)
            await session.commit()
            return next_token

    # Run 5 concurrent check-in tasks simultaneously
    tokens = await asyncio.gather(*[check_in_patient(i) for i in range(5)])

    # Verify that all 5 tokens are strictly sequential and unique (e.g. [1, 2, 3, 4, 5])
    assert len(set(tokens)) == 5
    assert sorted(tokens) == list(range(min(tokens), min(tokens) + 5))

    # Clean up test records
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM queue_entries WHERE doctor_id = :doc_id AND queue_date = :qdate;"),
            {"doc_id": data["doctor_id"], "qdate": test_date},
        )
        await session.execute(
            text("DELETE FROM appointments WHERE doctor_id = :doc_id AND appointment_date = :qdate;"),
            {"doc_id": data["doctor_id"], "qdate": test_date},
        )
        await session.commit()
