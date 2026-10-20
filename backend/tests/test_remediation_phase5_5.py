import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User

CLINIC_TZ = ZoneInfo("Asia/Kolkata")


def clinic_today_date():
    return datetime.now(CLINIC_TZ).date()


@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Ensure test-generated entities are purged after each test."""
    yield
    async with AsyncSessionLocal() as session:
        # Purge queue entries for test
        await session.execute(
            delete(QueueEntry).where(
                QueueEntry.notes.like("test_rem_%")
                | QueueEntry.id.in_(
                    select(QueueEntry.id).join(Appointment).where(
                        Appointment.appointment_token.like("REM-%")
                    )
                )
            )
        )
        # Purge test appointments
        await session.execute(
            delete(Appointment).where(Appointment.appointment_token.like("REM-%"))
        )
        # Purge test doctors
        await session.execute(
            delete(Doctor).where(Doctor.qualification.like("rem_doc_%"))
        )
        # Purge test users
        await session.execute(
            delete(User).where(User.email.like("rem_%@example.com"))
        )
        # Purge test hospitals
        await session.execute(
            delete(Hospital).where(Hospital.name.like("REM_HOSP_%"))
        )
        await session.commit()


async def create_test_hospital(tag: str) -> Hospital:
    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            id=uuid.uuid4(),
            name=f"REM_HOSP_{tag}_{uuid.uuid4().hex[:6]}",
            address="123 Test Street",
            city="Bengaluru",
            state="Karnataka",
            specialties=["General"],
            facilities=["OPD"],
            is_active=True,
        )
        session.add(hosp)
        await session.commit()
        await session.refresh(hosp)
        return hosp


async def create_test_doctor(hospital_id: uuid.UUID, tag: str) -> tuple[Doctor, User, str]:
    password = "DoctorPassword123!"
    hashed = get_password_hash(password)
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"rem_doc_{tag}_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hashed,
            full_name=f"Dr. Remediation {tag}",
            role="doctor",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        doc = Doctor(
            id=uuid.uuid4(),
            user_id=user.id,
            hospital_id=hospital_id,
            specialty="Cardiology",
            qualification=f"rem_doc_{tag}",
            experience_years=8,
            consultation_fee=500.0,
            is_available=True,
            credential_status="verified",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role="doctor")
    return doc, user, token


async def create_test_patient(tag: str) -> tuple[User, str]:
    password = "PatientPassword123!"
    hashed = get_password_hash(password)
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"rem_pat_{tag}_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hashed,
            full_name=f"Patient {tag}",
            role="patient",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role="patient")
    return user, token


async def create_test_hospital_admin(hospital_id: uuid.UUID | None, tag: str) -> tuple[User, str]:
    password = "AdminPassword123!"
    hashed = get_password_hash(password)
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"rem_adm_{tag}_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=hashed,
            full_name=f"Admin {tag}",
            role="hospital_admin",
            hospital_id=hospital_id,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role="hospital_admin", hospital_id=hospital_id)
    return user, token


async def create_test_appointment(
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    hospital_id: uuid.UUID,
    token_suffix: str,
) -> Appointment:
    today = clinic_today_date()
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            appointment_date=today,
            appointment_time=time(10, 0),
            status="scheduled",
            appointment_token=f"REM-{token_suffix}-{uuid.uuid4().hex[:4].upper()}",
            notes="Initial booking notes",
        )
        session.add(appt)
        await session.commit()
        await session.refresh(appt)
        return appt


# ===========================================================================
# STEP 2 — PATIENT CLINICAL NOTES PRIVACY TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_patient_queue_my_excludes_clinical_notes(client: AsyncClient):
    """Verify GET /api/v1/queue/my strictly excludes doctor clinical notes."""
    hosp = await create_test_hospital("priv")
    doc, doc_user, doc_token = await create_test_doctor(hosp.id, "priv")
    pat, pat_token = await create_test_patient("priv")
    appt = await create_test_appointment(pat.id, doc.id, hosp.id, "PRV1")

    # 1. Patient checks in
    checkin_res = await client.post(
        "/api/v1/queue/check-in",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"appointment_token": appt.appointment_token},
    )
    assert checkin_res.status_code == 201
    entry_id = checkin_res.json()["id"]

    # Verify check-in response does NOT contain notes
    assert "notes" not in checkin_res.json()

    # 2. Doctor calls patient and starts consultation with private notes
    secret_notes = "test_rem_CONFIDENTIAL_DIAGNOSIS: Patient has acute cardiac arrhythmia."
    call_res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"notes": secret_notes},
    )
    assert call_res.status_code == 200
    assert call_res.json()["notes"] == secret_notes
    assert call_res.json()["status"] == "in_consultation"

    # 3. Patient queries GET /api/v1/queue/my
    my_res = await client.get(
        "/api/v1/queue/my",
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert my_res.status_code == 200
    my_data = my_res.json()

    # CRITICAL SECURITY ASSERTIONS:
    # 1. 'notes' key must not be present in the JSON response
    assert "notes" not in my_data, "Clinical notes leaked in GET /api/v1/queue/my payload!"
    # 2. The string of notes must not appear anywhere in raw response body
    assert "CONFIDENTIAL_DIAGNOSIS" not in my_res.text, "Clinical note text found in patient response!"
    assert my_data["status"] == "in_consultation"


@pytest.mark.asyncio
async def test_public_queue_excludes_clinical_notes(client: AsyncClient):
    """Verify GET /api/v1/queue/doctor/{doc.id}/public-board excludes notes and patient PII."""
    hosp = await create_test_hospital("pub")
    doc, doc_user, doc_token = await create_test_doctor(hosp.id, "pub")
    pat, pat_token = await create_test_patient("pub")
    appt = await create_test_appointment(pat.id, doc.id, hosp.id, "PUB1")

    # Check in and start consultation with notes
    ci = await client.post(
        "/api/v1/queue/check-in",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"appointment_token": appt.appointment_token},
    )
    assert ci.status_code == 201
    entry_id = ci.json()["id"]

    call_res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"notes": "test_rem_PUBLIC_LEAK_CHECK_SECRET_DIAGNOSIS"},
    )
    assert call_res.status_code == 200

    # Public monitor endpoint
    pub_res = await client.get(f"/api/v1/queue/doctor/{doc.id}/public-board")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()

    assert "PUBLIC_LEAK_CHECK" not in pub_res.text
    if pub_data["current_consultation"]:
        assert "notes" not in pub_data["current_consultation"]


@pytest.mark.asyncio
async def test_doctor_console_preserves_clinical_notes(client: AsyncClient):
    """Verify authorized doctor console retains and returns clinical notes."""
    hosp = await create_test_hospital("docpres")
    doc, doc_user, doc_token = await create_test_doctor(hosp.id, "docpres")
    pat, pat_token = await create_test_patient("docpres")
    appt = await create_test_appointment(pat.id, doc.id, hosp.id, "DCP1")

    ci = await client.post(
        "/api/v1/queue/check-in",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"appointment_token": appt.appointment_token},
    )
    entry_id = ci.json()["id"]

    notes_content = "test_rem_Patient advised rest and follow up in 7 days."
    call_res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"notes": notes_content},
    )
    assert call_res.status_code == 200
    assert call_res.json()["notes"] == notes_content

    # Doctor views their own queue
    queue_res = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert queue_res.status_code == 200
    q_data = queue_res.json()
    assert q_data["current_consultation"] is not None
    assert q_data["current_consultation"]["notes"] == notes_content


@pytest.mark.asyncio
async def test_cross_doctor_access_denial(client: AsyncClient):
    """Verify Doctor A cannot view or manipulate Doctor B's queue entries or notes."""
    hosp = await create_test_hospital("crossdoc")
    doc_a, _, token_a = await create_test_doctor(hosp.id, "docA")
    doc_b, _, token_b = await create_test_doctor(hosp.id, "docB")

    # Doctor B attempts to view Doctor A's queue
    res = await client.get(
        f"/api/v1/queue/doctor/{doc_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_notes_length_validation_rejects_over_1000_chars(client: AsyncClient):
    """Verify notes exceeding 1000 characters are rejected with HTTP 422."""
    hosp = await create_test_hospital("maxlen")
    doc, _, doc_token = await create_test_doctor(hosp.id, "maxlen")
    pat, pat_token = await create_test_patient("maxlen")
    appt = await create_test_appointment(pat.id, doc.id, hosp.id, "LEN1")

    ci = await client.post(
        "/api/v1/queue/check-in",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"appointment_token": appt.appointment_token},
    )
    entry_id = ci.json()["id"]

    # Notes length = 1005 chars
    oversized_notes = "X" * 1005
    res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"notes": oversized_notes},
    )
    assert res.status_code == 422


# ===========================================================================
# STEP 3 — HOSPITAL AFFILIATION & AUTHORIZATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_hospital_admin_login_includes_persistent_affiliation(client: AsyncClient):
    """Verify hospital admin login returns token and user.hospital_id from database."""
    hosp = await create_test_hospital("hospadm")
    admin_user, _ = await create_test_hospital_admin(hosp.id, "hospadm")

    # Log in via POST /api/v1/auth/login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "AdminPassword123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert data["user"]["hospital_id"] == str(hosp.id)


@pytest.mark.asyncio
async def test_hospital_admin_authorized_for_affiliated_hospital_doctors(client: AsyncClient):
    """Verify hospital admin can access queues of doctors belonging to their hospital."""
    hosp = await create_test_hospital("affil_ok")
    doc, _, _ = await create_test_doctor(hosp.id, "affil_ok")
    admin, token = await create_test_hospital_admin(hosp.id, "affil_ok")

    res = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["doctor_id"] == str(doc.id)


@pytest.mark.asyncio
async def test_hospital_admin_cross_hospital_access_denied(client: AsyncClient):
    """Verify hospital admin cannot access queues of doctors belonging to another hospital."""
    hosp_a = await create_test_hospital("cross_a")
    hosp_b = await create_test_hospital("cross_b")
    doc_b, _, _ = await create_test_doctor(hosp_b.id, "cross_b")
    admin_a, token_a = await create_test_hospital_admin(hosp_a.id, "cross_a")

    res = await client.get(
        f"/api/v1/queue/doctor/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res.status_code == 403
    assert "Doctor does not belong to your authorized hospital" in res.json()["detail"]


@pytest.mark.asyncio
async def test_hospital_admin_unaffiliated_fails_closed(client: AsyncClient):
    """Verify hospital admin without hospital affiliation in database fails closed with 403."""
    hosp = await create_test_hospital("unaffil")
    doc, _, _ = await create_test_doctor(hosp.id, "unaffil")
    admin_unaffil, token_unaffil = await create_test_hospital_admin(None, "unaffil")

    res = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={"Authorization": f"Bearer {token_unaffil}"},
    )
    assert res.status_code == 403
    assert "no verified hospital affiliation configured" in res.json()["detail"]


@pytest.mark.asyncio
async def test_hospital_admin_revoked_affiliation_immediately_fails_closed(client: AsyncClient):
    """Verify that revoking hospital affiliation in the DB immediately revokes access for existing JWTs."""
    hosp = await create_test_hospital("revoke")
    doc, _, _ = await create_test_doctor(hosp.id, "revoke")
    admin, token = await create_test_hospital_admin(hosp.id, "revoke")

    # Access is initially granted
    res1 = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200

    # Revoke affiliation in database (set hospital_id = NULL)
    async with AsyncSessionLocal() as session:
        user_row = (await session.execute(select(User).where(User.id == admin.id))).scalar_one()
        user_row.hospital_id = None
        await session.commit()

    # Next request with the SAME token must immediately fail closed (401 or 403)
    res2 = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code in (401, 403), f"Expected 401 or 403 after revocation, got {res2.status_code}"


@pytest.mark.asyncio
async def test_client_header_spoofing_rejected(client: AsyncClient):
    """Verify client-supplied headers like X-Hospital-Id are ignored and cannot grant access."""
    hosp = await create_test_hospital("spoof")
    doc, _, _ = await create_test_doctor(hosp.id, "spoof")
    admin_unaffil, token = await create_test_hospital_admin(None, "spoof")

    # Admin attempts to pass X-Hospital-Id header to claim affiliation to hosp.id
    res = await client.get(
        f"/api/v1/queue/doctor/{doc.id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Hospital-Id": str(hosp.id),
        },
    )
    assert res.status_code == 403
    assert "no verified hospital affiliation configured" in res.json()["detail"]


@pytest.mark.asyncio
async def test_registration_blocks_administrative_roles(client: AsyncClient):
    """Verify public registration strictly blocks self-assignment of administrative roles."""
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rem_hack_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123!",
            "full_name": "Attacker",
            "role": "hospital_admin",
        },
    )
    assert res.status_code == 403
    assert "Administrative roles cannot be self-assigned" in res.json()["detail"]
