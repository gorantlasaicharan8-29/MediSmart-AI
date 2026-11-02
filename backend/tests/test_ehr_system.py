"""
Comprehensive automated tests for Phase 10: Clinical Consultation Notes & EHR System.

Tests:
1. Physician consultation note documentation with structured diagnoses and prescriptions.
2. Strict doctor appointment ownership validation (Doctor B cannot document Doctor A's patient).
3. Patient isolation on EHR history endpoints (Patient B cannot view Patient A's records).
4. Treating doctor authorization on patient EHR history.
5. Digital prescription generation with medication details and unique Rx tokens.
6. Follow-up care planning and official follow-up appointment booking with notifications.
7. Hospital admin data isolation across hospital boundaries.
8. Status synchronization of appointment to 'completed' upon consultation note documentation.
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
from app.models.ehr import (
    ConsultationNote,
    Diagnosis,
    Prescription,
    PrescriptionItem,
)
from app.models.hospital import Hospital
from app.models.notification import Notification
from app.models.user import User


@pytest.fixture(autouse=True)
async def cleanup_ehr_test_data():
    """Cleanup fixture for test records created in EHR test suite."""
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PrescriptionItem))
        await session.execute(delete(Prescription).where(Prescription.prescription_number.like("RX-%")))
        await session.execute(delete(Diagnosis).where(Diagnosis.diagnosis_name.like("EHR-TEST-%")))
        await session.execute(delete(ConsultationNote).where(ConsultationNote.chief_complaint.like("EHR-TEST-%")))
        await session.execute(delete(Notification).where(Notification.title.like("%Prescription%") | Notification.title.like("%Follow-Up%")))
        await session.execute(delete(Appointment).where(Appointment.appointment_token.like("EHR-APT-%")))
        await session.execute(delete(Doctor).where(Doctor.qualification.like("EHR-QUAL-%")))
        await session.execute(delete(Hospital).where(Hospital.name.like("EHR Test Hospital%")))
        await session.execute(delete(User).where(User.email.like("test_ehr_%")))
        await session.commit()


async def create_user_helper(role: str = "patient", hospital_id: uuid.UUID = None) -> tuple[User, dict]:
    """Creates a user and returns (user, auth_headers)."""
    uid = uuid.uuid4()
    email = f"test_ehr_{role}_{uuid.uuid4().hex[:6]}@example.com"
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
            name=f"EHR Test Hospital {name_suffix}",
            city="Metropolis",
            state="Central",
            address=f"20{name_suffix} Healthcare Blvd",
            phone="9876543210",
            email=f"hospital_ehr_{name_suffix}_{uuid.uuid4().hex[:4]}@example.com",
            specialties=["Cardiology", "Neurology", "General Medicine"],
            facilities=["ICU", "Pharmacy", "Laboratory"],
            is_active=True,
        )
        session.add(hosp)
        await session.commit()
        await session.refresh(hosp)
    return hosp


async def create_doctor_helper(hospital_id: uuid.UUID, specialty: str = "Cardiology") -> tuple[Doctor, User, dict]:
    """Creates a doctor and returns (doctor, user, auth_headers)."""
    doc_user, headers = await create_user_helper(role="doctor", hospital_id=hospital_id)
    doc_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        doctor = Doctor(
            id=doc_id,
            user_id=doc_user.id,
            hospital_id=hospital_id,
            qualification=f"EHR-QUAL-{uuid.uuid4().hex[:6]}",
            specialty=specialty,
            experience_years=12,
            consultation_fee=1500.0,
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
    appointment_date: date = None,
    appointment_time: time = time(10, 0),
    status: str = "scheduled",
) -> Appointment:
    """Creates an appointment record."""
    aid = uuid.uuid4()
    token = f"EHR-APT-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as session:
        appt = Appointment(
            id=aid,
            appointment_token=token,
            patient_id=patient_id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,
            appointment_date=appointment_date or date.today(),
            appointment_time=appointment_time,
            status=status,
            notes="Initial consultation request",
        )
        session.add(appt)
        await session.commit()
        await session.refresh(appt)
    return appt


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_doctor_create_consultation_note_with_rx_and_diagnoses(client: AsyncClient):
    """
    Physician documents a complete consultation note:
    - Chief complaint, observations, treatment plan.
    - Clinician diagnosis with ICD code.
    - Digital prescription with medication items.
    - Status of appointment synchronizes to 'completed'.
    """
    hosp = await create_hospital_helper("Main")
    doc, doc_user, headers_doc = await create_doctor_helper(hosp.id, specialty="Cardiology")
    pat, _ = await create_user_helper("patient")

    appt = await create_appointment_helper(pat.id, doc.id, hosp.id)

    payload = {
        "appointment_id": str(appt.id),
        "chief_complaint": "EHR-TEST- Patient experiencing chest tightness and exertion shortness of breath.",
        "symptoms": "Dyspnea on exertion, fatigue, intermittent palpitation.",
        "clinical_observations": "BP 138/88 mmHg, HR 78 bpm regular, normal heart sounds S1 S2.",
        "examination_notes": "Chest clear to auscultation bilaterally. No peripheral edema.",
        "diagnosis_summary": "Essential Hypertension and exertion fatigue.",
        "treatment_plan": "Lifestyle dietary sodium restriction, initiation of ACE inhibitor therapy.",
        "doctor_recommendations": "Light aerobic exercise 30 minutes daily. Monitor home blood pressure log.",
        "follow_up_recommended_date": (date.today() + timedelta(days=14)).isoformat(),
        "follow_up_instructions": "Review blood pressure diary and repeat electrolyte panel.",
        "diagnoses": [
            {
                "diagnosis_name": "EHR-TEST- Essential Primary Hypertension",
                "clinical_description": "Stage 1 essential hypertension documented during consultation.",
                "diagnosis_code": "ICD-10 I10",
                "status": "active",
            }
        ],
        "prescription": {
            "notes": "Take medication regularly in the morning with water.",
            "items": [
                {
                    "medication_name": "EHR-TEST- Lisinopril",
                    "dosage": "10mg",
                    "frequency": "Once daily in morning",
                    "duration": "30 days",
                    "route": "Oral",
                    "instructions": "Take with breakfast.",
                },
                {
                    "medication_name": "EHR-TEST- CoQ10 Supplement",
                    "dosage": "100mg",
                    "frequency": "Once daily",
                    "duration": "30 days",
                    "route": "Oral",
                    "instructions": "Dietary cardiovascular support.",
                }
            ],
        },
    }

    res = await client.post("/api/v1/ehr/consultations", json=payload, headers=headers_doc)
    assert res.status_code == 201
    data = res.json()

    assert data["appointment_id"] == str(appt.id)
    assert data["doctor_name"] == doc_user.full_name
    assert data["chief_complaint"] == payload["chief_complaint"]
    assert len(data["diagnoses"]) == 1
    assert data["diagnoses"][0]["diagnosis_code"] == "ICD-10 I10"

    assert len(data["prescriptions"]) == 1
    rx = data["prescriptions"][0]
    assert rx["prescription_number"].startswith("RX-")
    assert len(rx["items"]) == 2
    assert rx["items"][0]["medication_name"] == "EHR-TEST- Lisinopril"

    # Verify appointment status was synchronized to 'completed'
    async with AsyncSessionLocal() as session:
        updated_appt = await session.get(Appointment, appt.id)
        assert updated_appt.status == "completed"

        # Verify prescription notification was delivered to patient
        notif_res = await session.execute(
            select(Notification).where(
                Notification.user_id == pat.id,
                Notification.event_type == "prescription_issued",
            )
        )
        assert notif_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_doctor_ownership_validation_rejected_403(client: AsyncClient):
    """
    Doctor B cannot document a consultation note for Doctor A's appointment (403 Forbidden).
    """
    hosp = await create_hospital_helper("Ownership")
    doc1, _, _ = await create_doctor_helper(hosp.id)
    doc2, _, headers_doc2 = await create_doctor_helper(hosp.id)
    pat, _ = await create_user_helper("patient")

    appt_doc1 = await create_appointment_helper(pat.id, doc1.id, hosp.id)

    payload = {
        "appointment_id": str(appt_doc1.id),
        "chief_complaint": "EHR-TEST- Unauthorized consultation attempt",
        "diagnosis_summary": "Attempted documentation by non-assigned physician",
        "treatment_plan": "None",
    }

    # Doctor 2 attempts to document Doctor 1's appointment
    res = await client.post("/api/v1/ehr/consultations", json=payload, headers=headers_doc2)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_patient_medical_history_isolation(client: AsyncClient):
    """
    Patient A can view their own medical records.
    Patient B is forbidden from viewing Patient A's medical records (403).
    """
    hosp = await create_hospital_helper("History")
    doc, _, headers_doc = await create_doctor_helper(hosp.id)
    pat_a, headers_pat_a = await create_user_helper("patient")
    pat_b, headers_pat_b = await create_user_helper("patient")

    # Create consultation for Patient A
    appt_a = await create_appointment_helper(pat_a.id, doc.id, hosp.id)
    payload = {
        "appointment_id": str(appt_a.id),
        "chief_complaint": "EHR-TEST- Patient A routine evaluation",
        "diagnosis_summary": "Healthy adult wellness check",
        "treatment_plan": "Routine maintenance",
    }
    await client.post("/api/v1/ehr/consultations", json=payload, headers=headers_doc)

    # 1. Patient A accesses their own history via /my-history (200 OK)
    res_a = await client.get("/api/v1/ehr/my-history", headers=headers_pat_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["patient_id"] == str(pat_a.id)
    assert data_a["total_consultations"] >= 1

    # 2. Patient B attempts to access Patient A's history via /patient/{id}/history (403 Forbidden)
    res_b = await client.get(f"/api/v1/ehr/patient/{pat_a.id}/history", headers=headers_pat_b)
    assert res_b.status_code == 403
    assert "Access denied" in res_b.json()["detail"]


@pytest.mark.asyncio
async def test_treating_doctor_can_view_patient_history(client: AsyncClient):
    """
    A doctor who has an appointment with the patient is authorized to view their medical history.
    A doctor who has never treated the patient is rejected (403).
    """
    hosp = await create_hospital_helper("DoctorHistory")
    treating_doc, _, headers_treating = await create_doctor_helper(hosp.id)
    stranger_doc, _, headers_stranger = await create_doctor_helper(hosp.id)
    pat, _ = await create_user_helper("patient")

    # Create appointment linking treating_doc to patient
    await create_appointment_helper(pat.id, treating_doc.id, hosp.id)

    # 1. Treating doctor can view history (200 OK)
    res_treating = await client.get(f"/api/v1/ehr/patient/{pat.id}/history", headers=headers_treating)
    assert res_treating.status_code == 200
    assert res_treating.json()["patient_id"] == str(pat.id)

    # 2. Stranger doctor has no care relationship (403 Forbidden)
    res_stranger = await client.get(f"/api/v1/patient/{pat.id}/history", headers=headers_stranger)
    # Could be 404 on unmapped route or 403 on ehr route
    res_stranger_ehr = await client.get(f"/api/v1/ehr/patient/{pat.id}/history", headers=headers_stranger)
    assert res_stranger_ehr.status_code == 403
    assert "Access denied" in res_stranger_ehr.json()["detail"]


@pytest.mark.asyncio
async def test_follow_up_care_coordination_and_booking(client: AsyncClient):
    """
    Doctor recommends follow-up care and schedules a confirmed follow-up appointment.
    Verifies follow-up appointment is created in database and notification is dispatched.
    """
    hosp = await create_hospital_helper("FollowUp")
    doc, doc_user, headers_doc = await create_doctor_helper(hosp.id)
    pat, _ = await create_user_helper("patient")

    initial_appt = await create_appointment_helper(pat.id, doc.id, hosp.id)

    follow_up_date = date.today() + timedelta(days=21)
    payload = {
        "appointment_id": str(initial_appt.id),
        "recommended_date": follow_up_date.isoformat(),
        "recommended_time": "14:30",
        "instructions": "Re-evaluate Holter monitor readings.",
        "schedule_appointment": True,
    }

    res = await client.post("/api/v1/ehr/follow-up", json=payload, headers=headers_doc)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "scheduled"
    assert data["notification_dispatched"] is True
    assert data["follow_up_token"] is not None
    assert data["follow_up_appointment_id"] is not None

    # Verify new appointment in database
    async with AsyncSessionLocal() as session:
        new_appt = await session.get(Appointment, uuid.UUID(data["follow_up_appointment_id"]))
        assert new_appt is not None
        assert new_appt.appointment_date == follow_up_date
        assert new_appt.appointment_time == time(14, 30)
        assert new_appt.status == "scheduled"
        assert "Holter monitor" in new_appt.notes


@pytest.mark.asyncio
async def test_hospital_admin_scoping_on_ehr(client: AsyncClient):
    """
    Hospital Admin of Hospital A can view patient records for consultations at Hospital A.
    Hospital Admin of Hospital B is forbidden from viewing Hospital A's patient records (403).
    """
    hosp_a = await create_hospital_helper("HospitalAdminA")
    hosp_b = await create_hospital_helper("HospitalAdminB")

    doc_a, _, headers_doc_a = await create_doctor_helper(hosp_a.id)
    admin_a, headers_admin_a = await create_user_helper("hospital_admin", hospital_id=hosp_a.id)
    admin_b, headers_admin_b = await create_user_helper("hospital_admin", hospital_id=hosp_b.id)
    pat, _ = await create_user_helper("patient")

    appt = await create_appointment_helper(pat.id, doc_a.id, hosp_a.id)

    # Document consultation note at Hospital A
    doc_res = await client.post(
        "/api/v1/ehr/consultations",
        json={
            "appointment_id": str(appt.id),
            "chief_complaint": "EHR-TEST- Hospital scoping test",
            "diagnosis_summary": "Clinical evaluation",
            "treatment_plan": "Hospital scoping",
        },
        headers=headers_doc_a,
    )
    assert doc_res.status_code == 201
    note_id = doc_res.json()["id"]

    # Admin of Hospital A can view consultation (200 OK)
    res_admin_a = await client.get(f"/api/v1/ehr/consultations/{note_id}", headers=headers_admin_a)
    assert res_admin_a.status_code == 200

    # Admin of Hospital B is forbidden (403 Forbidden)
    res_admin_b = await client.get(f"/api/v1/ehr/consultations/{note_id}", headers=headers_admin_b)
    assert res_admin_b.status_code == 403


@pytest.mark.asyncio
async def test_get_consultation_by_appointment(client: AsyncClient):
    """Verifies fetching consultation note directly by appointment ID."""
    hosp = await create_hospital_helper("ByAppt")
    doc, _, headers_doc = await create_doctor_helper(hosp.id)
    pat, headers_pat = await create_user_helper("patient")

    appt = await create_appointment_helper(pat.id, doc.id, hosp.id)

    # Document consultation
    await client.post(
        "/api/v1/ehr/consultations",
        json={
            "appointment_id": str(appt.id),
            "chief_complaint": "EHR-TEST- By appointment lookup",
            "diagnosis_summary": "Diagnosis by appt",
            "treatment_plan": "Treatment plan by appt",
        },
        headers=headers_doc,
    )

    # Patient can retrieve by appointment ID
    res = await client.get(f"/api/v1/ehr/consultations/appointment/{appt.id}", headers=headers_pat)
    assert res.status_code == 200
    assert res.json()["appointment_id"] == str(appt.id)
    assert res.json()["chief_complaint"] == "EHR-TEST- By appointment lookup"

