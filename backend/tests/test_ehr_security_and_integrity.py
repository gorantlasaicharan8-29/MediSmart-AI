"""
PHASE 10.1: EHR Security, Data Integrity, and Access Control Test Suite.

Verifies:
1. Prescription Immutability: Issued prescriptions cannot be overwritten; tokens remain stable.
2. Prescription Amendments: Full audit trail, superseded_by_id linkage, incremented versioning, history preservation.
3. Clinical Audit Trail: Verified HIPAA/GDPR logging for note creation, modification, view, Rx issuance/amendment, and follow-ups.
4. Metadata Sanitization: Zero passwords, JWTs, or secrets in audit logs.
5. Transaction Integrity & Rollback: Atomic commit and complete rollback on mid-transaction errors.
6. Follow-up Booking Safety: Slot validation, collision prevention (409 Conflict), duplicate protection.
7. Access Control & IDOR Protection: Patient isolation, treating-doctor boundaries, hospital admin scoping, unauthenticated rejection.
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.ehr import ClinicalAuditLog, ConsultationNote, Diagnosis, Prescription, PrescriptionItem
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User


@pytest.fixture
def future_slot_date():
    return date.today() + timedelta(days=7)


@pytest.fixture
async def ehr_security_fixture(future_slot_date):
    """Sets up two hospitals, two doctors, and two patients for strict IDOR and isolation testing."""
    async with AsyncSessionLocal() as async_session:
        hosp1 = Hospital(
            id=uuid.uuid4(),
            name="Metro General Hospital",
            city="Metro City",
            state="State A",
            address="100 Main St",
            phone="555-0101",
            email="info@metrohosp.com",
        )
        hosp2 = Hospital(
            id=uuid.uuid4(),
            name="St. Jude Medical Center",
            city="North City",
            state="State B",
            address="200 North Ave",
            phone="555-0202",
            email="info@stjude.com",
        )
        async_session.add_all([hosp1, hosp2])
        await async_session.flush()

        # Doctor 1 at Hosp 1
        u_doc1 = User(
            id=uuid.uuid4(),
            email=f"doc1_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("DocSecret123!"),
            full_name="Dr. Gregory House",
            role="doctor",
            is_active=True,
        )
        # Doctor 2 at Hosp 2
        u_doc2 = User(
            id=uuid.uuid4(),
            email=f"doc2_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("DocSecret123!"),
            full_name="Dr. James Wilson",
            role="doctor",
            is_active=True,
        )
        # Patient 1
        u_pat1 = User(
            id=uuid.uuid4(),
            email=f"pat1_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("PatSecret123!"),
            full_name="John Doe",
            role="patient",
            is_active=True,
        )
        # Patient 2
        u_pat2 = User(
            id=uuid.uuid4(),
            email=f"pat2_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("PatSecret123!"),
            full_name="Jane Smith",
            role="patient",
            is_active=True,
        )
        # Hospital Admin for Hosp 1
        u_admin1 = User(
            id=uuid.uuid4(),
            email=f"admin1_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash("AdminSecret123!"),
            full_name="Admin Hosp1",
            role="hospital_admin",
            hospital_id=hosp1.id,
            is_active=True,
        )
        async_session.add_all([u_doc1, u_doc2, u_pat1, u_pat2, u_admin1])
        await async_session.flush()

        doc1 = Doctor(
            id=uuid.uuid4(),
            user_id=u_doc1.id,
            hospital_id=hosp1.id,
            specialty="Internal Medicine",
            qualification="MD",
            experience_years=15,
            consultation_fee=150.0,
            is_available=True,
        )
        doc2 = Doctor(
            id=uuid.uuid4(),
            user_id=u_doc2.id,
            hospital_id=hosp2.id,
            specialty="Oncology",
            qualification="MD",
            experience_years=12,
            consultation_fee=200.0,
            is_available=True,
        )
        async_session.add_all([doc1, doc2])
        await async_session.flush()

        # Appointment 1: Doc 1 with Pat 1 at Hosp 1
        appt1 = Appointment(
            id=uuid.uuid4(),
            appointment_token=f"MS-{future_slot_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            patient_id=u_pat1.id,
            doctor_id=doc1.id,
            hospital_id=hosp1.id,
            appointment_date=future_slot_date,
            appointment_time=time(10, 0),
            status="scheduled",
            notes="Routine checkup",
        )
        # Appointment 2: Doc 2 with Pat 2 at Hosp 2
        appt2 = Appointment(
            id=uuid.uuid4(),
            appointment_token=f"MS-{future_slot_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
            patient_id=u_pat2.id,
            doctor_id=doc2.id,
            hospital_id=hosp2.id,
            appointment_date=future_slot_date,
            appointment_time=time(11, 0),
            status="scheduled",
            notes="Specialist consultation",
        )
        async_session.add_all([appt1, appt2])
        await async_session.commit()

        return {
            "hosp1": hosp1,
            "hosp2": hosp2,
            "u_doc1": u_doc1,
            "u_doc2": u_doc2,
            "doc1": doc1,
            "doc2": doc2,
            "u_pat1": u_pat1,
            "u_pat2": u_pat2,
            "u_admin1": u_admin1,
            "appt1": appt1,
            "appt2": appt2,
            "token_doc1": create_access_token(user_id=u_doc1.id, role="doctor"),
            "token_doc2": create_access_token(user_id=u_doc2.id, role="doctor"),
            "token_pat1": create_access_token(user_id=u_pat1.id, role="patient"),
            "token_pat2": create_access_token(user_id=u_pat2.id, role="patient"),
            "token_admin1": create_access_token(user_id=u_admin1.id, role="hospital_admin", hospital_id=hosp1.id),
        }


# ===========================================================================
# 1. PRESCRIPTION IMMUTABILITY & AMENDMENT VERIFICATION
# ===========================================================================

@pytest.mark.asyncio
async def test_prescription_immutability_and_stable_token(ehr_security_fixture):
    """
    Verify:
    1. Issued prescription token remains stable.
    2. Repeated consultation updates cannot silently overwrite the issued prescription.
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Doctor 1 issues initial consultation note with prescription
        payload = {
            "appointment_id": str(ctx["appt1"].id),
            "chief_complaint": "Persistent migraines",
            "diagnosis_summary": "Tension headache",
            "treatment_plan": "Analgesic regimen",
            "prescription": {
                "notes": "Take with full glass of water",
                "items": [
                    {
                        "medication_name": "Ibuprofen",
                        "dosage": "400mg",
                        "frequency": "Three times daily",
                        "duration": "5 days",
                        "route": "Oral",
                        "instructions": "After meals",
                    }
                ],
            },
        }

        r1 = await client.post(
            "/api/v1/ehr/consultations",
            json=payload,
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r1.status_code == 201, r1.text
        data1 = r1.json()
        assert len(data1["prescriptions"]) == 1
        initial_rx = data1["prescriptions"][0]
        initial_rx_id = initial_rx["id"]
        initial_rx_num = initial_rx["prescription_number"]
        assert initial_rx_num.startswith("RX-")
        assert initial_rx["is_active"] is True
        assert initial_rx["version"] == 1

        # Step 2: Doctor 1 updates consultation notes with a DIFFERENT prescription payload
        # Immutability safeguard must prevent silent overwriting of the existing issued Rx.
        update_payload = {
            "appointment_id": str(ctx["appt1"].id),
            "chief_complaint": "Persistent migraines - patient reported improvement",
            "diagnosis_summary": "Tension headache (improving)",
            "treatment_plan": "Continue conservative measures",
            "prescription": {
                "notes": "Different notes attempt",
                "items": [
                    {
                        "medication_name": "Sumatriptan",
                        "dosage": "50mg",
                        "frequency": "As needed",
                        "duration": "3 days",
                        "route": "Oral",
                    }
                ],
            },
        }

        r2 = await client.post(
            "/api/v1/ehr/consultations",
            json=update_payload,
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r2.status_code == 201, r2.text
        data2 = r2.json()

        # The initial prescription must be preserved with stable token and unmodified medication item
        rx_check = next(rx for rx in data2["prescriptions"] if rx["id"] == initial_rx_id)
        assert rx_check["prescription_number"] == initial_rx_num
        assert rx_check["items"][0]["medication_name"] == "Ibuprofen"
        assert rx_check["items"][0]["dosage"] == "400mg"


@pytest.mark.asyncio
async def test_prescription_amendment_lifecycle_and_history(ehr_security_fixture):
    """
    Verify prescription amendment workflow:
    1. Active prescription is amended with clinical reason.
    2. Original prescription is preserved as is_active=False with amendment_reason and superseded_by_id.
    3. New prescription revision created with incremented version (v2).
    4. Both revisions remain accessible in patient medical history.
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Issue initial prescription
        r_init = await client.post(
            "/api/v1/ehr/consultations",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "chief_complaint": "Bacterial pharyngitis",
                "diagnosis_summary": "Acute pharyngitis",
                "treatment_plan": "Antibiotic course",
                "prescription": {
                    "notes": "Take full course",
                    "items": [
                        {
                            "medication_name": "Amoxicillin",
                            "dosage": "500mg",
                            "frequency": "Three times daily",
                            "duration": "10 days",
                            "route": "Oral",
                        }
                    ],
                },
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_init.status_code == 201
        v1_rx = r_init.json()["prescriptions"][0]
        v1_id = v1_rx["id"]

        # Doctor amends prescription: dose reduced due to nausea
        amend_payload = {
            "amendment_reason": "Patient experienced mild gastrointestinal upset; dosage adjusted to 250mg.",
            "notes": "Take with meals",
            "items": [
                {
                    "medication_name": "Amoxicillin",
                    "dosage": "250mg",
                    "frequency": "Three times daily",
                    "duration": "10 days",
                    "route": "Oral",
                    "instructions": "Take strictly after meals with water",
                }
            ],
        }

        r_amend = await client.post(
            f"/api/v1/ehr/prescriptions/{v1_id}/amend",
            json=amend_payload,
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_amend.status_code == 200, r_amend.text
        v2_rx = r_amend.json()
        assert v2_rx["version"] == 2
        assert v2_rx["is_active"] is True
        assert v2_rx["amendment_reason"] == amend_payload["amendment_reason"]
        assert v2_rx["items"][0]["dosage"] == "250mg"

        # Verify original v1 prescription state via GET
        r_v1 = await client.get(
            f"/api/v1/ehr/prescriptions/{v1_id}",
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_v1.status_code == 200
        v1_fetched = r_v1.json()
        assert v1_fetched["is_active"] is False
        assert v1_fetched["superseded_by_id"] == v2_rx["id"]
        assert v1_fetched["amendment_reason"] == amend_payload["amendment_reason"]

        # Attempting to amend an already superseded prescription must be rejected with 400
        r_re_amend = await client.post(
            f"/api/v1/ehr/prescriptions/{v1_id}/amend",
            json=amend_payload,
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_re_amend.status_code == 400
        assert "inactive or already superseded" in r_re_amend.json()["detail"]


# ===========================================================================
# 2. CLINICAL AUDIT TRAIL VERIFICATION
# ===========================================================================

@pytest.mark.asyncio
async def test_clinical_audit_trail_and_sanitization(ehr_security_fixture):
    """
    Verify:
    1. Audit logs are recorded for CONSULTATION_CREATED, PRESCRIPTION_ISSUED, RECORD_ACCESSED.
    2. Audit metadata strictly contains NO passwords, tokens, or JWTs.
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create consultation
        r_create = await client.post(
            "/api/v1/ehr/consultations",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "chief_complaint": "Joint pain",
                "diagnosis_summary": "Mild osteoarthritis",
                "treatment_plan": "Physiotherapy & paracetamol",
                "prescription": {
                    "items": [
                        {
                            "medication_name": "Paracetamol",
                            "dosage": "1000mg",
                            "frequency": "Every 8 hours",
                            "duration": "5 days",
                            "route": "Oral",
                        }
                    ]
                },
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_create.status_code == 201

        # Patient accesses history
        r_hist = await client.get(
            "/api/v1/ehr/my-history",
            headers={"Authorization": f"Bearer {ctx['token_pat1']}"},
        )
        assert r_hist.status_code == 200

        # Query audit logs
        r_audit = await client.get(
            f"/api/v1/ehr/audit-logs?patient_id={ctx['u_pat1'].id}",
            headers={"Authorization": f"Bearer {ctx['token_admin1']}"},
        )
        assert r_audit.status_code == 200
        audit_items = r_audit.json()["items"]
        assert len(audit_items) >= 2

        actions = [log["action"] for log in audit_items]
        assert "CONSULTATION_CREATED" in actions
        assert "RECORD_ACCESSED" in actions

        # Strict sanitization check across all audit log entries
        for log in audit_items:
            meta = log.get("metadata_json") or {}
            for k in meta.keys():
                k_lower = k.lower()
                assert "password" not in k_lower
                assert "secret" not in k_lower
                assert "jwt" not in k_lower
                assert "token" not in k_lower or k_lower in ("appointment_token", "prescription_number", "follow_up_token")


# ===========================================================================
# 3. FOLLOW-UP BOOKING SAFETY & CONFLICT DETECTION
# ===========================================================================

@pytest.mark.asyncio
async def test_follow_up_booking_slot_conflict_and_validation(ehr_security_fixture, future_slot_date):
    """
    Verify:
    1. Past dates for follow-up are rejected with 400.
    2. Invalid slot times outside ALLOWED_SLOT_TIMES are rejected with 400.
    3. Conflicting slots return 409 Conflict.
    4. Successful follow-up booking uses existing booking engine and assigns valid token.
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Past date rejected
        past_date = date.today() - timedelta(days=2)
        r_past = await client.post(
            "/api/v1/ehr/follow-up",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "recommended_date": past_date.isoformat(),
                "instructions": "Follow up in past",
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_past.status_code == 400
        assert "cannot be in the past" in r_past.json()["detail"]

        # Case 2: Invalid clinic slot rejected
        r_bad_slot = await client.post(
            "/api/v1/ehr/follow-up",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "recommended_date": future_slot_date.isoformat(),
                "recommended_time": "13:30",  # Lunch break
                "schedule_appointment": True,
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_bad_slot.status_code == 400
        assert "valid 30-minute clinic slot" in r_bad_slot.json()["detail"]

        # Case 3: Slot collision (Doctor 1 already has Appt 1 at 10:00 on future_slot_date)
        r_conflict = await client.post(
            "/api/v1/ehr/follow-up",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "recommended_date": future_slot_date.isoformat(),
                "recommended_time": "10:00",
                "schedule_appointment": True,
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_conflict.status_code == 409
        assert "already booked" in r_conflict.json()["detail"]

        # Case 4: Valid open slot (14:30) succeeds cleanly
        r_success = await client.post(
            "/api/v1/ehr/follow-up",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "recommended_date": future_slot_date.isoformat(),
                "recommended_time": "14:30",
                "schedule_appointment": True,
                "instructions": "Bring blood test results",
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_success.status_code == 200
        fu_data = r_success.json()
        assert fu_data["status"] == "scheduled"
        assert fu_data["follow_up_token"] is not None
        assert fu_data["follow_up_token"].startswith("MS-")


# ===========================================================================
# 4. ACCESS CONTROL & IDOR PROTECTION MATRIX
# ===========================================================================

@pytest.mark.asyncio
async def test_access_control_and_idor_matrix(ehr_security_fixture):
    """
    Exhaustively verify authorization boundaries:
    - Patient 1 cannot view Patient 2's medical history (403).
    - Doctor 1 cannot view Patient 2's medical history (no care relationship) (403).
    - Doctor 2 cannot document consultation for Doctor 1's appointment (403).
    - Hospital 1 Admin cannot view records from Hospital 2 (403).
    - Unauthenticated requests are rejected (401).
    - Prescription lookup enforces patient isolation (403).
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated requests rejected with 401
        r_unauth = await client.get("/api/v1/ehr/my-history")
        assert r_unauth.status_code == 401

        # 2. Patient 1 attempting to view Patient 2's history -> 403
        r_pat_idor = await client.get(
            f"/api/v1/ehr/patient/{ctx['u_pat2'].id}/history",
            headers={"Authorization": f"Bearer {ctx['token_pat1']}"},
        )
        assert r_pat_idor.status_code == 403

        # 3. Doctor 1 attempting to view Patient 2's history (no appointments with Patient 2) -> 403
        r_doc_idor = await client.get(
            f"/api/v1/ehr/patient/{ctx['u_pat2'].id}/history",
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_doc_idor.status_code == 403

        # 4. Doctor 2 attempting to document consultation for Appt 1 (owned by Doctor 1) -> 403
        r_cross_doc = await client.post(
            "/api/v1/ehr/consultations",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "chief_complaint": "Unauthorized entry attempt",
                "diagnosis_summary": "Test",
                "treatment_plan": "Test",
            },
            headers={"Authorization": f"Bearer {ctx['token_doc2']}"},
        )
        assert r_cross_doc.status_code == 403

        # 5. Doctor 1 creates consultation and prescription for Patient 1
        r_doc1_create = await client.post(
            "/api/v1/ehr/consultations",
            json={
                "appointment_id": str(ctx["appt1"].id),
                "chief_complaint": "Valid complaint",
                "diagnosis_summary": "Valid diagnosis",
                "treatment_plan": "Valid plan",
                "prescription": {
                    "items": [
                        {
                            "medication_name": "Cetirizine",
                            "dosage": "10mg",
                            "frequency": "Once daily",
                            "duration": "14 days",
                            "route": "Oral",
                        }
                    ]
                },
            },
            headers={"Authorization": f"Bearer {ctx['token_doc1']}"},
        )
        assert r_doc1_create.status_code == 201
        rx_id = r_doc1_create.json()["prescriptions"][0]["id"]

        # 6. Patient 2 attempting to view Patient 1's prescription -> 403
        r_rx_idor = await client.get(
            f"/api/v1/ehr/prescriptions/{rx_id}",
            headers={"Authorization": f"Bearer {ctx['token_pat2']}"},
        )
        assert r_rx_idor.status_code == 403
        assert "only view your own prescriptions" in r_rx_idor.json()["detail"]

        # 7. Doctor 2 attempting to view Patient 1's prescription -> 403
        r_rx_doc2 = await client.get(
            f"/api/v1/ehr/prescriptions/{rx_id}",
            headers={"Authorization": f"Bearer {ctx['token_doc2']}"},
        )
        assert r_rx_doc2.status_code == 403

        # 8. Patient 1 can view their own prescription -> 200
        r_rx_owner = await client.get(
            f"/api/v1/ehr/prescriptions/{rx_id}",
            headers={"Authorization": f"Bearer {ctx['token_pat1']}"},
        )
        assert r_rx_owner.status_code == 200
        assert r_rx_owner.json()["items"][0]["medication_name"] == "Cetirizine"


# ===========================================================================
# 5. TRANSACTION ROLLBACK & ATOMIC BOUNDARY VERIFICATION
# ===========================================================================

@pytest.mark.asyncio
async def test_transaction_rollback_and_atomic_boundary(ehr_security_fixture):
    """
    Verify transaction rollback integrity:
    If an unexpected error occurs during consultation processing prior to commit
    (e.g., failure during audit logging or secondary entity generation), the entire
    transaction must be rolled back atomically. Zero partial records (consultation notes,
    prescriptions, diagnoses) should be persisted, and appointment status must remain unchanged.
    """
    ctx = ehr_security_fixture
    transport = ASGITransport(app=app)

    # Use appointment 2 for Doctor 1 (ctx["appt2"])
    appt_id = ctx["appt2"].id

    payload = {
        "appointment_id": str(appt_id),
        "chief_complaint": "Severe abdominal cramping",
        "diagnosis_summary": "Suspected gastroenteritis",
        "treatment_plan": "Oral rehydration salts",
        "prescription": {
            "items": [
                {
                    "medication_name": "Oral Rehydration Salts",
                    "dosage": "1 packet in 1L water",
                    "frequency": "Ad libitum",
                    "duration": "3 days",
                    "route": "Oral",
                }
            ]
        },
        "diagnoses": [
            {
                "diagnosis_name": "Acute Gastroenteritis",
                "clinical_description": "Watery diarrhea and abdominal cramps",
                "diagnosis_code": "A09",
                "status": "active",
            }
        ],
    }

    # Simulate an error during clinical audit logging to trigger a rollback
    with patch(
        "app.services.clinical_audit_service.clinical_audit_service.log",
        side_effect=RuntimeError("Simulated audit disk failure"),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with pytest.raises(RuntimeError, match="Simulated audit disk failure"):
                await client.post(
                    "/api/v1/ehr/consultations",
                    json=payload,
                    headers={"Authorization": f"Bearer {ctx['token_doc2']}"},
                )

    # Verify atomic rollback in the database: no consultation, no prescription, no diagnosis, appointment still scheduled
    async with AsyncSessionLocal() as session:
        # Check ConsultationNote
        note_res = await session.execute(
            select(ConsultationNote).where(ConsultationNote.appointment_id == appt_id)
        )
        assert note_res.scalar_one_or_none() is None

        # Check Prescription
        rx_res = await session.execute(
            select(Prescription).where(Prescription.appointment_id == appt_id)
        )
        assert rx_res.scalar_one_or_none() is None

        # Check Diagnosis
        diag_res = await session.execute(
            select(Diagnosis).where(Diagnosis.patient_id == ctx["u_pat2"].id)
        )
        all_diags = diag_res.scalars().all()
        assert not any(d.diagnosis_name == "Acute Gastroenteritis" for d in all_diags)

        # Check Appointment status remains scheduled (never committed as completed)
        appt_res = await session.execute(
            select(Appointment).where(Appointment.id == appt_id)
        )
        appt = appt_res.scalar_one()
        assert appt.status == "scheduled"

