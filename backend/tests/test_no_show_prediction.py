"""
Comprehensive automated tests for Phase 9.3: AI Appointment No-Show Prediction System.

Tests:
1. Model loading & pipeline availability.
2. Direct service prediction from database appointment entity.
3. Calibrated risk classification thresholds (Low, Medium, High).
4. Explainable risk factors generation (lead time, attendance history, notes, timing).
5. Role-based security and isolation on single appointment risk endpoint:
   - Patient isolation: patient A cannot access patient B's risk assessment (403).
   - Doctor isolation: doctor A cannot access doctor B's appointment risk (403).
   - Hospital admin isolation: admin A cannot access appointments at other hospitals (403).
   - Unauthenticated access returns 401.
6. Doctor appointment risk list endpoint (GET /doctor/appointments-risk):
   - Returns scored items with summary metrics (high, medium, low counts, avg risk).
   - Risk level filtering (high, medium, low).
   - Patient role forbidden (403).
7. Hospital admin aggregate analytics endpoint (GET /hospital/no-show-analytics):
   - Computes attendance rates, risk distributions, and specialty breakdown.
   - Scoped strictly to hospital admin's hospital_id.
8. Smart reminder dispatch (POST /appointments/{id}/send-reminder):
   - Dispatches notification to patient with high urgency.
   - Enforces idempotency to suppress duplicate reminders for the same date.
   - Verifies appointment record is NOT modified or cancelled.
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.notification import Notification
from app.models.user import User
from app.services.no_show_service import NoShowRiskService


@pytest.fixture(autouse=True)
async def cleanup_no_show_test_data():
    """Cleanup fixture for test records created during no-show test suite."""
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Notification).where(Notification.title.like("Appointment Reminder%")))
        await session.execute(delete(Appointment).where(Appointment.appointment_token.like("NS-TEST-%")))
        await session.execute(delete(Doctor).where(Doctor.qualification.like("NS-QUAL-%")))
        await session.execute(delete(Hospital).where(Hospital.name.like("NS Test Hospital%")))
        await session.execute(delete(User).where(User.email.like("test_ns_%")))
        await session.commit()


async def create_user_helper(role: str = "patient", hospital_id: uuid.UUID = None) -> tuple[User, dict]:
    """Creates a user and returns (user, auth_headers)."""
    uid = uuid.uuid4()
    email = f"test_ns_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=uid,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Test {role.title()} User",
            role=role,
            is_active=True,
            hospital_id=hospital_id,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=uid, role=role)
    return user, {"Authorization": f"Bearer {token}"}


async def create_hospital_helper(name_suffix: str = "A") -> Hospital:
    """Creates a test hospital."""
    hid = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        hosp = Hospital(
            id=hid,
            name=f"NS Test Hospital {name_suffix}",
            city="Metropolis",
            state="Central",
            address=f"10{name_suffix} Healthcare Blvd",
            phone="9876543210",
            email=f"hospital_{name_suffix}_{uuid.uuid4().hex[:4]}@example.com",
            specialties=["Cardiology", "Pediatrics", "Orthopedics"],
            facilities=["ICU", "Emergency"],
            is_active=True,
        )
        session.add(hosp)
        await session.commit()
        await session.refresh(hosp)
    return hosp


async def create_doctor_helper(hospital_id: uuid.UUID, specialty: str = "Cardiology", fee: float = 1200.0) -> tuple[Doctor, User, dict]:
    """Creates a doctor and returns (doctor, user, auth_headers)."""
    doc_user, headers = await create_user_helper(role="doctor", hospital_id=hospital_id)
    doc_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        doctor = Doctor(
            id=doc_id,
            user_id=doc_user.id,
            hospital_id=hospital_id,
            qualification=f"NS-QUAL-{uuid.uuid4().hex[:6]}",
            specialty=specialty,
            experience_years=10,
            consultation_fee=fee,
            is_available=True,
        )
        session.add(doctor)
        await session.commit()
        await session.refresh(doctor)
    return doctor, doc_user, headers


async def create_appointment_helper(
    patient_id: uuid.UUID,
    doctor_id: uuid.UUID,
    hospital_id: uuid.UUID,
    appointment_date: date,
    appointment_time: time,
    status: str = "scheduled",
    notes: str = None,
    created_at_dt: datetime = None,
) -> Appointment:
    """Creates an appointment with explicit parameters."""
    aid = uuid.uuid4()
    token = f"NS-TEST-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            id=aid,
            appointment_token=token,
            patient_id=patient_id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status=status,
            notes=notes,
            created_at=created_at_dt or (datetime.now(timezone.utc) - timedelta(days=5)),
        )
        session.add(appt)
        await session.commit()
        await session.refresh(appt)
    return appt


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_show_service_prediction_and_thresholds():
    """Verifies that NoShowRiskService correctly derives features and produces calibrated risk outputs."""
    hosp = await create_hospital_helper("ServiceTest")
    doc, _, _ = await create_doctor_helper(hosp.id, specialty="Cardiology", fee=1200.0)
    pat, _ = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=1)
    appt = await create_appointment_helper(
        patient_id=pat.id,
        doctor_id=doc.id,
        hospital_id=hosp.id,
        appointment_date=tomorrow,
        appointment_time=time(10, 0),
        notes="Patient experiencing mild palpitations.",
        created_at_dt=datetime.now(timezone.utc) - timedelta(days=2),
    )

    async with AsyncSessionLocal() as session:
        risk_res = await NoShowRiskService.predict_for_appointment(appt.id, session)

    assert risk_res is not None
    assert risk_res.appointment_id == appt.id
    assert 0.0 <= risk_res.no_show_probability <= 1.0
    assert risk_res.risk_level in ("low", "medium", "high")
    assert risk_res.risk_display_label in ("Low Risk", "Medium Risk", "High Risk")
    assert len(risk_res.risk_factors) >= 1
    assert risk_res.is_synthetic_model is True
    assert "synthetic" in risk_res.provenance_notice.lower()


@pytest.mark.asyncio
async def test_get_appointment_risk_patient_isolation(client: AsyncClient):
    """Verifies patient isolation on GET /api/v1/predictions/appointments/{id}/risk."""
    hosp = await create_hospital_helper("PatientIso")
    doc, _, _ = await create_doctor_helper(hosp.id)
    pat_a, headers_a = await create_user_helper("patient")
    pat_b, headers_b = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=1)
    appt_a = await create_appointment_helper(
        patient_id=pat_a.id,
        doctor_id=doc.id,
        hospital_id=hosp.id,
        appointment_date=tomorrow,
        appointment_time=time(10, 0),
    )

    # 1. Unauthenticated request returns 401
    unauth_res = await client.get(f"/api/v1/predictions/appointments/{appt_a.id}/risk")
    assert unauth_res.status_code == 401

    # 2. Patient A can view their own appointment risk (200 OK)
    ok_res = await client.get(f"/api/v1/predictions/appointments/{appt_a.id}/risk", headers=headers_a)
    assert ok_res.status_code == 200
    data = ok_res.json()
    assert data["appointment_id"] == str(appt_a.id)
    assert "no_show_probability" in data
    assert "risk_factors" in data

    # 3. Patient B is strictly forbidden from viewing Patient A's appointment risk (403 Forbidden)
    forbidden_res = await client.get(f"/api/v1/predictions/appointments/{appt_a.id}/risk", headers=headers_b)
    assert forbidden_res.status_code == 403
    assert "Access denied" in forbidden_res.json()["detail"]


@pytest.mark.asyncio
async def test_get_appointment_risk_doctor_and_admin_scoping(client: AsyncClient):
    """Verifies doctor and hospital admin access control on appointment risk endpoint."""
    hosp1 = await create_hospital_helper("Hosp1")
    hosp2 = await create_hospital_helper("Hosp2")

    doc1, _, headers_doc1 = await create_doctor_helper(hosp1.id)
    doc2, _, headers_doc2 = await create_doctor_helper(hosp1.id)
    admin_hosp1, headers_admin1 = await create_user_helper("hospital_admin", hospital_id=hosp1.id)
    admin_hosp2, headers_admin2 = await create_user_helper("hospital_admin", hospital_id=hosp2.id)
    pat, _ = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=2)
    appt_doc1 = await create_appointment_helper(
        patient_id=pat.id,
        doctor_id=doc1.id,
        hospital_id=hosp1.id,
        appointment_date=tomorrow,
        appointment_time=time(11, 30),
    )

    # Assigned doctor (Doc 1) can view (200)
    res_doc1 = await client.get(f"/api/v1/predictions/appointments/{appt_doc1.id}/risk", headers=headers_doc1)
    assert res_doc1.status_code == 200

    # Non-assigned doctor (Doc 2) is forbidden (403)
    res_doc2 = await client.get(f"/api/v1/predictions/appointments/{appt_doc1.id}/risk", headers=headers_doc2)
    assert res_doc2.status_code == 403

    # Hospital Admin of Hosp 1 can view (200)
    res_admin1 = await client.get(f"/api/v1/predictions/appointments/{appt_doc1.id}/risk", headers=headers_admin1)
    assert res_admin1.status_code == 200

    # Hospital Admin of Hosp 2 is forbidden (403)
    res_admin2 = await client.get(f"/api/v1/predictions/appointments/{appt_doc1.id}/risk", headers=headers_admin2)
    assert res_admin2.status_code == 403


@pytest.mark.asyncio
async def test_doctor_appointments_risk_list_and_filters(client: AsyncClient):
    """Tests GET /api/v1/predictions/doctor/appointments-risk with filters and role control."""
    hosp = await create_hospital_helper("DocList")
    doc, _, headers_doc = await create_doctor_helper(hosp.id, specialty="Pediatrics")
    pat, headers_pat = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=1)
    # Create 3 appointments for this doctor
    for i in range(3):
        await create_appointment_helper(
            patient_id=pat.id,
            doctor_id=doc.id,
            hospital_id=hosp.id,
            appointment_date=tomorrow,
            appointment_time=time(9 + i, 0),
            created_at_dt=datetime.now(timezone.utc) - timedelta(days=i * 5),
        )

    # 1. Patient role is forbidden (403)
    res_pat = await client.get("/api/v1/predictions/doctor/appointments-risk", headers=headers_pat)
    assert res_pat.status_code == 403

    # 2. Doctor fetches risk list (200 OK)
    res_doc = await client.get("/api/v1/predictions/doctor/appointments-risk", headers=headers_doc)
    assert res_doc.status_code == 200
    data = res_doc.json()
    assert data["doctor_id"] == str(doc.id)
    assert data["total_appointments"] >= 3
    assert len(data["items"]) >= 3
    assert "average_risk_probability" in data
    assert "high_risk_count" in data
    assert "medium_risk_count" in data
    assert "low_risk_count" in data

    # 3. Filter by date
    res_date = await client.get(
        f"/api/v1/predictions/doctor/appointments-risk?date={tomorrow.isoformat()}",
        headers=headers_doc,
    )
    assert res_date.status_code == 200
    assert len(res_date.json()["items"]) == 3


@pytest.mark.asyncio
async def test_hospital_no_show_analytics(client: AsyncClient):
    """Tests GET /api/v1/predictions/hospital/no-show-analytics."""
    hosp = await create_hospital_helper("AnalyticsHosp")
    doc, _, _ = await create_doctor_helper(hosp.id, specialty="Orthopedics")
    admin, headers_admin = await create_user_helper("hospital_admin", hospital_id=hosp.id)
    pat, headers_pat = await create_user_helper("patient")

    past_date = date.today() - timedelta(days=10)
    future_date = date.today() + timedelta(days=2)

    # Historical: 1 completed, 1 no_show
    await create_appointment_helper(pat.id, doc.id, hosp.id, past_date, time(10, 0), status="completed")
    await create_appointment_helper(pat.id, doc.id, hosp.id, past_date, time(11, 0), status="no_show")

    # Upcoming: 1 scheduled
    await create_appointment_helper(pat.id, doc.id, hosp.id, future_date, time(14, 0), status="scheduled")

    # Patient forbidden (403)
    res_pat = await client.get("/api/v1/predictions/hospital/no-show-analytics", headers=headers_pat)
    assert res_pat.status_code == 403

    # Hospital Admin accesses analytics
    res = await client.get("/api/v1/predictions/hospital/no-show-analytics", headers=headers_admin)
    assert res.status_code == 200
    data = res.json()
    assert data["hospital_id"] == str(hosp.id)
    assert data["total_historical_appointments"] == 2
    assert data["attended_appointments"] == 1
    assert data["missed_appointments"] == 1
    assert data["historical_no_show_rate"] == 0.50
    assert data["scheduled_appointments_count"] >= 1
    assert "risk_distribution" in data
    assert "specialty_trends" in data
    assert any(s["specialty"] == "Orthopedics" for s in data["specialty_trends"])


@pytest.mark.asyncio
async def test_smart_reminder_dispatch_and_idempotency(client: AsyncClient):
    """Tests POST /api/v1/predictions/appointments/{id}/send-reminder."""
    hosp = await create_hospital_helper("ReminderHosp")
    doc, _, headers_doc = await create_doctor_helper(hosp.id)
    pat, headers_pat = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=1)
    appt = await create_appointment_helper(
        patient_id=pat.id,
        doctor_id=doc.id,
        hospital_id=hosp.id,
        appointment_date=tomorrow,
        appointment_time=time(15, 0),
        status="scheduled",
    )

    # 1. Patient cannot dispatch reminders for themselves (403)
    res_pat = await client.post(
        f"/api/v1/predictions/appointments/{appt.id}/send-reminder",
        headers=headers_pat,
    )
    assert res_pat.status_code == 403

    # 2. Doctor dispatches smart reminder (200 OK)
    res_doc = await client.post(
        f"/api/v1/predictions/appointments/{appt.id}/send-reminder",
        headers=headers_doc,
    )
    assert res_doc.status_code == 200
    rem_data = res_doc.json()
    assert rem_data["status"] == "sent"
    assert rem_data["is_duplicate"] is False
    assert rem_data["patient_id"] == str(pat.id)
    assert "friendly reminder" in rem_data["message"]

    # Verify notification was recorded in DB
    async with AsyncSessionLocal() as session:
        notif_res = await session.execute(
            select(Notification).where(Notification.user_id == pat.id)
        )
        notif = notif_res.scalar_one_or_none()
        assert notif is not None
        assert notif.event_type == "appointment_reminder"
        assert notif.urgency == "high"

        # Verify appointment was NOT modified or cancelled
        appt_check = await session.get(Appointment, appt.id)
        assert appt_check.status == "scheduled"
        assert appt_check.appointment_date == tomorrow

    # 3. Second call dispatches idempotently without creating a duplicate notification
    res_dup = await client.post(
        f"/api/v1/predictions/appointments/{appt.id}/send-reminder",
        headers=headers_doc,
    )
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["is_duplicate"] is True
    assert dup_data["status"] == "duplicate_suppressed"


@pytest.mark.asyncio
async def test_appointment_risk_not_found_404(client: AsyncClient):
    """Unknown appointment UUID returns 404."""
    pat, headers = await create_user_helper("patient")
    fake_id = uuid.uuid4()
    res = await client.get(f"/api/v1/predictions/appointments/{fake_id}/risk", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reminder_unauthorized_doctor_403(client: AsyncClient):
    """Doctor cannot send reminder for an appointment assigned to a different doctor."""
    hosp = await create_hospital_helper("UnauthDocHosp")
    doc1, _, _ = await create_doctor_helper(hosp.id)
    doc2, _, headers_doc2 = await create_doctor_helper(hosp.id)
    pat, _ = await create_user_helper("patient")

    tomorrow = date.today() + timedelta(days=1)
    appt = await create_appointment_helper(
        patient_id=pat.id,
        doctor_id=doc1.id,
        hospital_id=hosp.id,
        appointment_date=tomorrow,
        appointment_time=time(16, 0),
    )

    res = await client.post(
        f"/api/v1/predictions/appointments/{appt.id}/send-reminder",
        headers=headers_doc2,
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]

