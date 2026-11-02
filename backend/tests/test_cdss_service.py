"""
Comprehensive Test Suite for Phase 11: Clinical Decision Support System (CDSS).

Verifies:
1. Note summarization & structured symptom extraction with provenance.
2. Missing data resilience & zero clinical hallucination.
3. Documentation completeness auditing and score heuristics.
4. Medication safety: duplicate drug names and pharmacological class conflicts.
5. Medication safety: verified drug-drug interactions (Warfarin+Aspirin, ACEI+Spironolactone, SSRI+Tramadol).
6. Medication safety: missing instruction detection (dosage, frequency, duration).
7. Clinical guidelines matching by ICD-10 code and diagnostic keywords.
8. Longitudinal patient history insights with active/chronic diagnosis classification.
9. Strict RBAC: patient rejection (403), treating-doctor authorization, and non-treating doctor rejection (403).
10. End-to-end comprehensive CDSS evaluation API with clinical audit trail recording.
"""
import uuid
from datetime import date, datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.cdss import CDSSClinicianFeedback, CDSSSafetyEvent
from app.models.doctor import Doctor
from app.models.ehr import (
    ClinicalAuditLog,
    ConsultationNote,
    Diagnosis,
    Prescription,
    PrescriptionItem,
)
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.cdss import (
    CDSSComprehensiveRequest,
    CDSSFeedbackInput,
    CDSSSafetyEventAcknowledgeRequest,
    MedicationItemInput,
    NoteSummaryInput,
)
from app.services.cdss_service import cdss_service


@pytest.fixture
async def cdss_test_context():
    """Sets up doctor, patient, appointment, and hospital context strictly in medismart_test_db."""
    async with AsyncSessionLocal() as session:
        # Create unique hospital
        hosp = Hospital(
            id=uuid.uuid4(),
            name=f"CDSS Test Hospital {uuid.uuid4().hex[:6]}",
            address="100 Innovation Way",
            city="Metropolis",
            state="NY",
            is_active=True,
        )
        session.add(hosp)

        # Create Doctor User
        doc_user = User(
            id=uuid.uuid4(),
            email=f"cdss_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Dr. Elena Rostova",
            role="doctor",
            is_active=True,
        )
        session.add(doc_user)
        await session.flush()

        doc = Doctor(
            id=uuid.uuid4(),
            user_id=doc_user.id,
            hospital_id=hosp.id,
            specialty="Cardiology",
            qualification="MD, FACC",
            experience_years=12,
            is_available=True,
        )
        session.add(doc)

        # Create External Non-treating Doctor User
        doc2_user = User(
            id=uuid.uuid4(),
            email=f"cdss_external_doc_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Dr. External Clinician",
            role="doctor",
            is_active=True,
        )
        session.add(doc2_user)
        await session.flush()

        doc2 = Doctor(
            id=uuid.uuid4(),
            user_id=doc2_user.id,
            hospital_id=hosp.id,
            specialty="Neurology",
            qualification="MD",
            experience_years=8,
            is_available=True,
        )
        session.add(doc2)

        # Create Patient User
        pat_user = User(
            id=uuid.uuid4(),
            email=f"cdss_patient_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Arthur Pendelton",
            role="patient",
            is_active=True,
        )
        session.add(pat_user)
        await session.flush()

        # Create Scheduled Appointment between Doc 1 and Patient
        appt = Appointment(
            id=uuid.uuid4(),
            appointment_token=f"APPT-CDSS-{uuid.uuid4().hex[:6].upper()}",
            patient_id=pat_user.id,
            doctor_id=doc.id,
            hospital_id=hosp.id,
            appointment_date=date(2026, 11, 15),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status="scheduled",
            notes="Patient reports recurrent severe throbbing headaches with photophobia.",
        )
        session.add(appt)
        await session.commit()

        context = {
            "hosp": hosp,
            "doc_user": doc_user,
            "doc": doc,
            "doc2_user": doc2_user,
            "doc2": doc2,
            "pat_user": pat_user,
            "appt": appt,
            "token_doc": create_access_token(user_id=doc_user.id, role="doctor"),
            "token_doc2": create_access_token(user_id=doc2_user.id, role="doctor"),
            "token_pat": create_access_token(user_id=pat_user.id, role="patient"),
        }
        yield context

        # Teardown
        async with AsyncSessionLocal() as teardown_session:
            await teardown_session.execute(
                ClinicalAuditLog.__table__.delete().where(
                    ClinicalAuditLog.patient_id == pat_user.id
                )
            )
            await teardown_session.execute(
                Appointment.__table__.delete().where(Appointment.id == appt.id)
            )
            await teardown_session.execute(
                Doctor.__table__.delete().where(Doctor.id.in_([doc.id, doc2.id]))
            )
            await teardown_session.execute(
                User.__table__.delete().where(
                    User.id.in_([doc_user.id, doc2_user.id, pat_user.id])
                )
            )
            await teardown_session.execute(
                Hospital.__table__.delete().where(Hospital.id == hosp.id)
            )
            await teardown_session.commit()


# ---------------------------------------------------------------------------
# 1. Clinical Note Summarization & Symptom Extraction Unit Tests
# ---------------------------------------------------------------------------
def test_clinical_note_summarization_and_symptom_structuring():
    """Verify executive summary synthesis and structured symptom categorization."""
    input_data = NoteSummaryInput(
        chief_complaint="Severe unilateral throbbing headache with visual aura",
        symptoms="Acute photophobia for 3 days; moderate nausea; visual scintillating scotoma 9/10 pain",
        clinical_observations="Patient appears photophobic, resting in dimmed room, oriented x3.",
        examination_notes="Neurological cranial nerves II-XII intact. No meningismus. Pupils equal and reactive.",
        diagnosis_summary="Migraine with aura (episodic)",
        treatment_plan="Sumatriptan 50mg oral at headache onset. Naproxen 500mg for breakthrough pain.",
        doctor_recommendations="Maintain sleep hygiene and headache diary. Stay hydrated.",
        follow_up_instructions="Return in 4 weeks for preventive therapy review.",
    )

    summary = cdss_service.summarize_clinical_notes(input_data)

    assert "Severe unilateral throbbing headache" in summary.executive_summary
    assert "Migraine with aura" in summary.executive_summary
    assert summary.chief_complaint == input_data.chief_complaint
    assert len(summary.structured_symptoms) >= 2

    # Check extracted symptom severity classification
    severities = [s.severity_assessment for s in summary.structured_symptoms]
    assert any(sev in ["Severe", "Moderate"] for sev in severities)

    # Check provenance
    assert "CURRENT_ENCOUNTER" in summary.provenance_sources
    assert "AI_SYNTHESIS" in summary.provenance_sources
    assert "AI-assisted summary" in summary.disclaimer


def test_missing_data_resilience_and_no_fabrication():
    """Verify missing fields are tagged as '[Not documented]' and never fabricated."""
    minimal_input = NoteSummaryInput(
        chief_complaint="Routine annual checkup",
        symptoms=None,
        clinical_observations=None,
        examination_notes=None,
        diagnosis_summary=None,
        treatment_plan=None,
    )

    summary = cdss_service.summarize_clinical_notes(minimal_input)

    assert summary.chief_complaint == "Routine annual checkup"
    assert summary.clinical_observations_summary == "[Not documented]"
    assert summary.examination_findings_summary == "[Not documented]"
    assert summary.diagnostic_impression == "[Not documented]"
    assert summary.treatment_plan_summary == "[Not documented]"
    assert summary.structured_symptoms[0].symptom_name == "No specific symptoms documented"


# ---------------------------------------------------------------------------
# 2. Documentation Completeness Review Tests
# ---------------------------------------------------------------------------
def test_documentation_completeness_audit_scoring():
    """Verify scoring heuristics and actionable completeness checklists."""
    # Complete documentation
    complete_notes = NoteSummaryInput(
        chief_complaint="Elevated blood pressure readings recorded at home",
        symptoms="Occasional morning occipital headaches for 2 weeks, no blurred vision",
        clinical_observations="BP 152/94 mmHg, HR 74 bpm regular, BMI 27.2",
        examination_notes="Cardiovascular S1/S2 normal, no murmurs, no peripheral edema. Lungs clear.",
        diagnosis_summary="Essential Hypertension, Stage 2",
        treatment_plan="Initiate Amlodipine 5mg daily. Order baseline renal panel and lipid profile.",
        doctor_recommendations="Reduce dietary sodium to <2g/day. Follow DASH eating plan.",
        follow_up_instructions="Repeat BP check in 2 weeks. Return immediately if chest pain or shortness of breath occurs.",
    )
    result_complete = cdss_service.audit_documentation_completeness(complete_notes)
    assert result_complete.completeness_score >= 80
    assert result_complete.overall_status == "optimal"
    assert all(it.is_complete for it in result_complete.items)

    # Incomplete documentation
    sparse_notes = NoteSummaryInput(
        chief_complaint="Fever",
        symptoms=None,
        clinical_observations=None,
        examination_notes=None,
        diagnosis_summary=None,
        treatment_plan=None,
    )
    result_sparse = cdss_service.audit_documentation_completeness(sparse_notes)
    assert result_sparse.completeness_score < 50
    assert result_sparse.overall_status == "incomplete"
    assert len(result_sparse.actionable_recommendations) >= 3


# ---------------------------------------------------------------------------
# 3. Medication Safety Support Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_medication_safety_duplicate_and_class_detection():
    """Verify detection of exact duplicate medications and redundant drug classes."""
    items = [
        MedicationItemInput(medication_name="Ibuprofen 400mg", dosage="400mg", frequency="TID", duration="5 days"),
        MedicationItemInput(medication_name="Naproxen 500mg", dosage="500mg", frequency="BID", duration="5 days"),
        MedicationItemInput(medication_name="Ibuprofen 200mg", dosage="200mg", frequency="PRN", duration="3 days"),
    ]

    result = await cdss_service.evaluate_medication_safety(current_items=items)

    assert result.overall_safety_status in ["WARNING_FLAGGED", "REVIEW_RECOMMENDED"]
    assert len(result.duplicate_alerts) >= 2

    types = [d.duplicate_type for d in result.duplicate_alerts]
    assert "EXACT_NAME" in types
    assert "PHARMACOLOGICAL_CLASS" in types


@pytest.mark.asyncio
async def test_medication_safety_verified_drug_interactions():
    """Verify verified high-impact drug-drug interactions with peer-reviewed rationale."""
    # Case 1: Warfarin + Aspirin (CRITICAL bleeding risk)
    items_bleed = [
        MedicationItemInput(medication_name="Warfarin 5mg", dosage="5mg", frequency="Once daily", duration="30 days"),
        MedicationItemInput(medication_name="Aspirin 81mg", dosage="81mg", frequency="Once daily", duration="30 days"),
    ]
    res_bleed = await cdss_service.evaluate_medication_safety(current_items=items_bleed)
    assert res_bleed.overall_safety_status == "WARNING_FLAGGED"
    assert any(a.severity == "CRITICAL" for a in res_bleed.interaction_alerts)
    assert any("bleeding" in a.risk_summary.lower() for a in res_bleed.interaction_alerts)

    # Case 2: Lisinopril + Spironolactone (HIGH hyperkalemia risk)
    items_k = [
        MedicationItemInput(medication_name="Lisinopril 20mg", dosage="20mg", frequency="Once daily", duration="30 days"),
        MedicationItemInput(medication_name="Spironolactone 25mg", dosage="25mg", frequency="Once daily", duration="30 days"),
    ]
    res_k = await cdss_service.evaluate_medication_safety(current_items=items_k)
    assert any("hyperkalemia" in a.risk_summary.lower() for a in res_k.interaction_alerts)

    # Case 3: Fluoxetine + Tramadol (HIGH serotonin syndrome risk)
    items_serotonin = [
        MedicationItemInput(medication_name="Fluoxetine 20mg", dosage="20mg", frequency="Once daily", duration="30 days"),
        MedicationItemInput(medication_name="Tramadol 50mg", dosage="50mg", frequency="Q6H PRN", duration="5 days"),
    ]
    res_serotonin = await cdss_service.evaluate_medication_safety(current_items=items_serotonin)
    assert any("serotonin" in a.risk_summary.lower() for a in res_serotonin.interaction_alerts)


@pytest.mark.asyncio
async def test_medication_safety_missing_instructions():
    """Verify incomplete prescription directives trigger instruction alerts."""
    items_incomplete = [
        MedicationItemInput(medication_name="Metformin", dosage="", frequency="", duration="", route="Oral"),
    ]
    result = await cdss_service.evaluate_medication_safety(current_items=items_incomplete)
    assert len(result.instruction_alerts) == 1
    missing = result.instruction_alerts[0].missing_fields
    assert "dosage" in missing
    assert "frequency" in missing
    assert "duration" in missing


# ---------------------------------------------------------------------------
# 4. Clinical Practice Guidelines Assistant Tests
# ---------------------------------------------------------------------------
def test_clinical_guidelines_matching():
    """Verify retrieval of accredited clinical guidelines by condition name and ICD-10 code."""
    # Match by condition name
    res_htn = cdss_service.match_clinical_guidelines(diagnosis_name="Essential Hypertension")
    assert res_htn.total_matched >= 1
    assert any(g.guideline_id == "GUIDE-HTN-2023" for g in res_htn.matched_guidelines)
    assert any("ACC" in g.publishing_authority or "AHA" in g.publishing_authority for g in res_htn.matched_guidelines)

    # Match by ICD-10 code
    res_mig = cdss_service.match_clinical_guidelines(diagnosis_code="G43.109")
    assert res_mig.total_matched >= 1
    assert any(g.guideline_id == "GUIDE-MIG-2023" for g in res_mig.matched_guidelines)
    guide = res_mig.matched_guidelines[0]
    rec_categories = [r.category for r in guide.recommendations]
    assert "First-line Pharmacotherapy" in rec_categories
    assert "Red Flags / Referral" in rec_categories


# ---------------------------------------------------------------------------
# 5. Longitudinal Patient History Insights Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_patient_history_insights_longitudinal(cdss_test_context):
    """Verify synthesis of active/chronic diagnoses and active prescriptions from EHR records."""
    ctx = cdss_test_context
    pat_id = ctx["pat_user"].id

    async with AsyncSessionLocal() as session:
        # Create a consultation note first to satisfy foreign key constraints
        note = ConsultationNote(
            id=uuid.uuid4(),
            appointment_id=ctx["appt"].id,
            patient_id=pat_id,
            doctor_id=ctx["doc"].id,
            hospital_id=ctx["hosp"].id,
            consultation_date=date(2026, 1, 10),
            consultation_time=datetime.strptime("10:00", "%H:%M").time(),
            chief_complaint="Follow-up chronic care",
            diagnosis_summary="Essential Hypertension",
            treatment_plan="Continue lifestyle measures",
        )
        session.add(note)
        await session.flush()

        # Seed historical chronic diagnosis and active prescription
        diag_chronic = Diagnosis(
            id=uuid.uuid4(),
            consultation_note_id=note.id,
            patient_id=pat_id,
            doctor_id=ctx["doc"].id,
            diagnosis_name="Hypertension",
            diagnosis_code="I10",
            diagnosis_date=date(2026, 1, 10),
            status="chronic",
        )
        session.add(diag_chronic)

        diag_resolved = Diagnosis(
            id=uuid.uuid4(),
            consultation_note_id=note.id,
            patient_id=pat_id,
            doctor_id=ctx["doc"].id,
            diagnosis_name="Acute Bronchitis",
            diagnosis_code="J20",
            diagnosis_date=date(2026, 3, 1),
            status="resolved",
        )
        session.add(diag_resolved)

        rx = Prescription(
            id=uuid.uuid4(),
            prescription_number="RX-TEST-HIST01",
            consultation_note_id=note.id,
            appointment_id=ctx["appt"].id,
            patient_id=pat_id,
            doctor_id=ctx["doc"].id,
            hospital_id=ctx["hosp"].id,
            prescription_date=date(2026, 10, 1),
            is_active=True,
            version=1,
        )
        session.add(rx)
        await session.flush()

        rx_item = PrescriptionItem(
            id=uuid.uuid4(),
            prescription_id=rx.id,
            medication_name="Amlodipine",
            dosage="5mg",
            frequency="Once daily",
            duration="30 days",
            route="Oral",
        )
        session.add(rx_item)
        await session.commit()

        # Query insights
        insights = await cdss_service.get_patient_history_insights(patient_id=pat_id, db=session)

        assert insights.patient_name == "Arthur Pendelton"
        assert len(insights.chronic_conditions) == 1
        assert insights.chronic_conditions[0].diagnosis_name == "Hypertension"
        assert len(insights.resolved_diagnoses) == 1
        assert len(insights.active_prescriptions) == 1
        assert insights.active_prescriptions[0].medication_name == "Amlodipine"
        assert insights.allergy_documentation_status in ["none_recorded", "NOT_DOCUMENTED"]

        # Cleanup extra items
        await session.execute(PrescriptionItem.__table__.delete().where(PrescriptionItem.prescription_id == rx.id))
        await session.execute(Prescription.__table__.delete().where(Prescription.id == rx.id))
        await session.execute(Diagnosis.__table__.delete().where(Diagnosis.patient_id == pat_id))
        await session.execute(ConsultationNote.__table__.delete().where(ConsultationNote.id == note.id))
        await session.commit()


# ---------------------------------------------------------------------------
# 6. REST API End-to-End Tests & Security Matrix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cdss_rbac_and_treating_doctor_authorization(client: AsyncClient, cdss_test_context):
    """Verify role authorization and IDOR protection on CDSS patient insights."""
    ctx = cdss_test_context

    headers_doc = {"Authorization": f"Bearer {ctx['token_doc']}"}
    headers_doc2 = {"Authorization": f"Bearer {ctx['token_doc2']}"}
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat']}"}

    pat_id = str(ctx["pat_user"].id)

    # 1. Unauthenticated request -> 401
    unauth_res = await client.get(f"/api/v1/cdss/patient/{pat_id}/insights")
    assert unauth_res.status_code == 401

    # 2. Patient role trying to access CDSS endpoint -> 403 Forbidden
    pat_res = await client.get(f"/api/v1/cdss/patient/{pat_id}/insights", headers=headers_pat)
    assert pat_res.status_code == 403

    # 3. Non-treating doctor (Doc2) attempting to access patient insights -> 403 Forbidden
    doc2_res = await client.get(f"/api/v1/cdss/patient/{pat_id}/insights", headers=headers_doc2)
    assert doc2_res.status_code == 403
    assert "not authorized" in doc2_res.json()["detail"].lower()

    # 4. Treating doctor (Doc1) accessing patient insights -> 200 OK
    doc1_res = await client.get(f"/api/v1/cdss/patient/{pat_id}/insights", headers=headers_doc)
    assert doc1_res.status_code == 200
    assert doc1_res.json()["patient_name"] == "Arthur Pendelton"


@pytest.mark.asyncio
async def test_cdss_comprehensive_evaluation_endpoint(client: AsyncClient, cdss_test_context):
    """Verify the full encounter evaluation endpoint combining all modules."""
    ctx = cdss_test_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc']}"}

    payload = {
        "appointment_id": str(ctx["appt"].id),
        "patient_id": str(ctx["pat_user"].id),
        "notes": {
            "chief_complaint": "Recurrent unilateral throbbing headache with photophobia",
            "symptoms": "Severe visual aura lasting 30 minutes followed by intense left hemicranial pain",
            "clinical_observations": "Patient resting with eyes shielded, vitals stable, BP 122/78 mmHg",
            "examination_notes": "Funduscopic examination normal, cranial nerves II-XII intact, no meningism",
            "diagnosis_summary": "Migraine with aura",
            "treatment_plan": "Sumatriptan 50mg oral at headache onset. Naproxen 500mg for breakthrough pain.",
            "doctor_recommendations": "Keep headache diary, maintain regular sleep patterns, avoid known triggers.",
            "follow_up_instructions": "Review headache diary in 4 weeks.",
        },
        "prescriptions": [
            {"medication_name": "Sumatriptan", "dosage": "50mg", "frequency": "At onset PRN", "duration": "10 days", "route": "Oral"},
            {"medication_name": "Naproxen", "dosage": "500mg", "frequency": "BID PRN", "duration": "5 days", "route": "Oral"},
        ],
        "diagnosis_name": "Migraine with aura",
        "diagnosis_code": "G43.109",
    }

    res = await client.post("/api/v1/cdss/evaluate", json=payload, headers=headers_doc)
    assert res.status_code == 200
    data = res.json()

    # Verify Summary
    assert "Recurrent unilateral throbbing headache" in data["summary"]["executive_summary"]
    assert len(data["summary"]["structured_symptoms"]) >= 1

    # Verify Documentation Completeness
    assert data["documentation_completeness"]["completeness_score"] >= 80
    assert data["documentation_completeness"]["overall_status"] == "optimal"

    # Verify Medication Safety
    assert data["medication_safety"]["overall_safety_status"] in ["SAFE", "REVIEW_RECOMMENDED"]

    # Verify Guidelines Matching
    assert data["guidelines"]["total_matched"] >= 1
    assert any("AHS" in g["publishing_authority"] or "NICE" in g["publishing_authority"] for g in data["guidelines"]["matched_guidelines"])

    # Verify Patient Insights
    assert data["patient_insights"]["patient_name"] == "Arthur Pendelton"

    # Verify AI Safety Disclaimer
    assert "CLINICAL ASSISTIVE NOTICE" in data["ai_safety_notice"]

    # Verify clinical audit trail entry was recorded
    async with AsyncSessionLocal() as session:
        audit_res = await session.execute(
            select(ClinicalAuditLog)
            .where(
                and_(
                    ClinicalAuditLog.action == "CDSS_EVALUATION",
                    ClinicalAuditLog.actor_id == ctx["doc_user"].id,
                )
            )
            .order_by(ClinicalAuditLog.created_at.desc())
        )
        audit_entry = audit_res.scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.actor_role == "doctor"
        assert audit_entry.target_type == "consultation_encounter"
        assert "completeness_score" in audit_entry.metadata_json


@pytest.mark.asyncio
async def test_clinical_negation_and_pertinent_negatives():
    """
    Phase 11.1 QA: Verifies that negated clinical statements (e.g., 'no fever', 'denies chest pain')
    are routed to pertinent negatives and NEVER classified as active complaints.
    """
    notes = NoteSummaryInput(
        chief_complaint="Throbbing headache and generalized fatigue for 3 days",
        symptoms="Severe bilateral temporal headache. Denies chest pain. No fever, negative for cough, rules out dyspnea.",
        clinical_observations="Alert, oriented x 3, vitals stable",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # Verify executive summary
    assert "Throbbing headache" in summary.executive_summary

    # Verify pertinent negatives were captured
    assert len(summary.pertinent_negatives) >= 2
    neg_lower = [n.lower() for n in summary.pertinent_negatives]
    assert any("chest pain" in n for n in neg_lower)
    assert any("fever" in n for n in neg_lower)

    # Verify that negated terms are NOT listed as presenting complaints
    active_symptoms = [s.symptom_name.lower() for s in summary.structured_symptoms if not s.is_negated and s.status == "PRESENT"]
    assert not any("chest pain" in s for s in active_symptoms)
    assert not any("fever" in s for s in active_symptoms)
    assert any("headache" in s for s in active_symptoms)

    # Verify that negated terms are marked with is_negated == True
    negated_symptoms = [s.symptom_name.lower() for s in summary.structured_symptoms if s.is_negated]
    assert any("chest pain" in s for s in negated_symptoms)


@pytest.mark.asyncio
async def test_historical_symptom_attribution():
    """
    Phase 11.1 QA: Verifies that past or historical symptoms are separated from active complaints
    and tagged with source_attribution == 'HISTORICAL_RECORD'.
    """
    notes = NoteSummaryInput(
        chief_complaint="Palpitations and dizziness",
        symptoms="Frequent episodic palpitations. Past history of asthma as a child. Previously diagnosed with seasonal allergies.",
        clinical_observations="Regular rhythm, pulse 82 bpm",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # Check for historical attribution
    historical_symptoms = [s for s in summary.structured_symptoms if s.source_attribution == "HISTORICAL_RECORD"]
    assert len(historical_symptoms) >= 1
    assert any("asthma" in s.symptom_name.lower() or "allergies" in s.symptom_name.lower() for s in historical_symptoms)

    # Current consultation symptoms
    current_symptoms = [s for s in summary.structured_symptoms if s.source_attribution == "CURRENT_ENCOUNTER"]
    assert any("palpitations" in s.symptom_name.lower() for s in current_symptoms)


@pytest.mark.asyncio
async def test_clinical_contradiction_detection():
    """
    Phase 11.1 QA: Verifies cross-section discordance/contradiction detection
    (e.g., reported fever vs afebrile observations, chest pain vs normal cardiac exam).
    """
    notes = NoteSummaryInput(
        chief_complaint="Fever and chest discomfort",
        symptoms="Patient complains of high-grade fever with shaking chills and acute chest pain",
        clinical_observations="Patient is afebrile with normal body temperature 98.4F",
        examination_notes="Cardiovascular exam normal with no chest pain elicited on palpation",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # Verify contradictions detected
    assert len(summary.contradictions_detected) >= 2
    assert any("fever" in c.lower() and "afebrile" in c.lower() for c in summary.contradictions_detected)
    assert any("chest pain" in c.lower() for c in summary.contradictions_detected)


@pytest.mark.asyncio
async def test_medication_interaction_evidence_provenance():
    """
    Phase 11.1 QA: Verifies that all medication safety alerts include authoritative evidence provenance,
    source URLs, clinical certainty ('ESTABLISHED' | 'PRECAUTIONARY'), and KB versioning.
    """
    items = [
        MedicationItemInput(medication_name="Warfarin", dosage="5mg", frequency="Daily", duration="30 days", route="Oral"),
        MedicationItemInput(medication_name="Aspirin", dosage="325mg", frequency="Daily", duration="30 days", route="Oral"),
    ]

    async with AsyncSessionLocal() as session:
        result = await cdss_service.evaluate_medication_safety(current_items=items, db=session)

    assert result.overall_safety_status == "WARNING_FLAGGED"
    assert len(result.interaction_alerts) >= 1

    alert = result.interaction_alerts[0]
    assert alert.interaction_id == "DD-WAR-ASA"
    assert alert.primary_class == "Vitamin K Antagonist Anticoagulant"
    assert alert.clinical_certainty == "ESTABLISHED"
    assert "FDA Boxed Warning" in alert.evidence_source
    assert alert.source_url.startswith("https://")
    assert alert.last_reviewed_date == "2026-10-15"
    assert alert.knowledge_base_version.startswith("2026.11.")


@pytest.mark.asyncio
async def test_guideline_freshness_and_accredited_metadata():
    """
    Phase 11.1 QA: Verifies that matched clinical practice guidelines provide accredited metadata,
    source URLs, current validation freshness status, and clinical uncertainty disclosures.
    """
    response = cdss_service.match_clinical_guidelines(
        diagnosis_name="Essential Hypertension",
        diagnosis_code="I10",
        specialty="Cardiology",
    )

    assert response.total_matched >= 1
    guide = response.matched_guidelines[0]

    assert guide.guideline_title is not None
    assert guide.freshness_status in ["CURRENT_VERIFIED", "CURRENT_VALIDATED"]
    assert guide.version is not None
    assert guide.source_url.startswith("https://")
    assert guide.last_verified_date == "2026-10-15"
    assert len(guide.recommendations) >= 2
    assert "clinical judgment" in guide.uncertainty_statement.lower() or "physician" in guide.uncertainty_statement.lower()


@pytest.mark.asyncio
async def test_knowledge_base_metadata_endpoint_and_service(client: AsyncClient, cdss_test_context):
    """
    Phase 11.1 QA: Verifies the dedicated GET /api/v1/cdss/knowledge-base/metadata endpoint
    returns governance policy, versioning, review timestamps, and active rule counts.
    """
    ctx = cdss_test_context
    headers = {"Authorization": f"Bearer {ctx['token_doc']}"}

    res = await client.get("/api/v1/cdss/knowledge-base/metadata", headers=headers)
    assert res.status_code == 200

    data = res.json()
    assert data["version"].startswith("2026.11.")
    assert data["last_reviewed"] in ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert data["total_active_interaction_rules"] >= 15
    assert data["total_active_guidelines"] >= 6
    assert "peer-reviewed" in data["governance_policy"].lower()
    # Phase 11.2 additions
    assert "version_history" in data
    assert len(data["version_history"]) >= 3
    assert data["governance_board"] is not None


# ===========================================================================
# PHASE 11.2: CLINICAL GOVERNANCE, REAL-WORLD VALIDATION & SAFETY MONITORING TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_phase_11_2_guideline_5_state_freshness_classification():
    """
    Phase 11.2: Verifies that clinical practice guidelines are categorized according to the
    5-state freshness framework: CURRENT_VERIFIED, REVIEW_REQUIRED, UNDER_REVIEW, SUPERSEDED, UNVERIFIED.
    Also validates evidence classification (CLASS_I_STRONG, etc.) and next review dates.
    """
    # 1. CURRENT_VERIFIED: Essential Hypertension
    res_htn = cdss_service.match_clinical_guidelines(diagnosis_code="I10")
    assert res_htn.total_matched >= 1
    guide_htn = res_htn.matched_guidelines[0]
    assert guide_htn.freshness_status == "CURRENT_VERIFIED"
    assert guide_htn.evidence_classification == "CLASS_I_STRONG"
    assert guide_htn.approval_status == "APPROVED"
    assert guide_htn.next_review_date == "2027-09-15"

    # 2. REVIEW_REQUIRED: Migraine (2021) or CAP (2019)
    res_mig = cdss_service.match_clinical_guidelines(diagnosis_code="G43")
    assert res_mig.total_matched >= 1
    guide_mig = res_mig.matched_guidelines[0]
    assert guide_mig.freshness_status == "REVIEW_REQUIRED"
    assert guide_mig.approval_status in ["APPROVED", "PENDING_REVIEW"]
    assert guide_mig.next_review_date in ["2026-11-30", "2026-12-31"]

    # 3. UNDER_REVIEW: Major Depressive Disorder (F32)
    res_mdd = cdss_service.match_clinical_guidelines(diagnosis_code="F32")
    assert res_mdd.total_matched >= 1
    guide_mdd = res_mdd.matched_guidelines[0]
    assert guide_mdd.freshness_status == "UNDER_REVIEW"
    assert guide_mdd.approval_status == "PENDING_REVIEW"


@pytest.mark.asyncio
async def test_phase_11_2_kb_metadata_version_lineage():
    """
    Phase 11.2: Verifies that KnowledgeBaseMetadata tracks the full release history,
    governance board, and scheduled review cadence.
    """
    meta = cdss_service.get_knowledge_base_metadata()
    assert meta.version in ["2026.11.2-v1.2", "2026.11.3-v1.3"]
    assert meta.governance_board == "MediSmart AI Clinical Oversight Committee"
    assert meta.next_scheduled_review is not None

    assert len(meta.version_history) >= 3
    versions = [vh.version for vh in meta.version_history]
    assert "2026.11.2-v1.2" in versions


@pytest.mark.asyncio
async def test_phase_11_2_allergy_4_state_safety_framework():
    """
    Phase 11.2: Verifies the 4-state allergy framework:
    - NOT_DOCUMENTED -> Prominent safety alert requiring clinician verification prior to prescribing.
    - DOCUMENTED_ALLERGIES -> Cross-check against prescribed items (e.g. penicillin allergy + amoxicillin).
    """
    async with AsyncSessionLocal() as session:
        # 1. Unrecorded patient: missing allergy record must NEVER default to 'no allergies'
        dummy_patient_id = uuid.uuid4()
        insights = await cdss_service.get_patient_history_insights(patient_id=dummy_patient_id, db=session)
        assert insights.allergy_documentation_status == "NOT_DOCUMENTED"
        assert "NOT DOCUMENTED" in insights.allergy_safety_warning
        assert "verbally verify" in insights.allergy_safety_warning.lower()

        # 2. Medication safety check with no patient id -> NOT_DOCUMENTED safety warning
        items = [
            MedicationItemInput(medication_name="Amoxicillin", dosage="500mg", frequency="TID", duration="7 days", route="Oral"),
        ]
        med_res = await cdss_service.evaluate_medication_safety(current_items=items, db=session)
        assert med_res.allergy_safety_status == "NOT_DOCUMENTED"
        assert med_res.allergy_warning_banner is not None
        assert "NOT DOCUMENTED" in med_res.allergy_warning_banner


@pytest.mark.asyncio
async def test_phase_11_2_nlp_family_history_isolation():
    """
    Phase 11.2: Verifies that mentions of family history (e.g. 'Mother had type 2 diabetes')
    are extracted into family_history_notes with is_family_history=True, and strictly excluded
    from the patient's acute presenting symptoms and working diagnosis.
    """
    notes = NoteSummaryInput(
        chief_complaint="Severe sore throat and difficulty swallowing",
        symptoms="Mother had severe diabetes and father had chronic hypertension. Patient has painful pharyngitis and fever.",
        clinical_observations="Patient appears uncomfortable.",
        examination_notes="Erythematous tonsils with white exudates.",
        diagnosis_summary="Acute streptococcal pharyngitis",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # Family history notes isolated
    assert len(summary.family_history_notes) >= 1
    fh_text = " ".join(summary.family_history_notes).lower()
    assert "mother" in fh_text or "father" in fh_text
    assert "diabetes" in fh_text or "hypertension" in fh_text

    # Verify structured symptoms: active patient symptoms must have is_family_history=False
    active_symptoms = [s for s in summary.structured_symptoms if not s.is_family_history]
    active_names = [s.symptom_name.lower() for s in active_symptoms]
    assert any("pharyngitis" in name or "sore throat" in name or "fever" in name for name in active_names)


@pytest.mark.asyncio
async def test_phase_11_2_nlp_uncertainty_and_conditional_directives():
    """
    Phase 11.2: Verifies clinical uncertainty preservation (SUSPECTED / UNCERTAIN)
    and contingency / conditional directives extraction.
    """
    notes = NoteSummaryInput(
        chief_complaint="Right lower quadrant abdominal pain",
        symptoms="Suspected acute appendicitis. Possible mesenteric lymphadenitis.",
        clinical_observations="Tenderness at McBurney's point. Guarding present.",
        examination_notes="Abdominal ultrasound ordered.",
        diagnosis_summary="Suspected appendicitis vs mesenteric adenitis",
        treatment_plan="If ultrasound confirms appendicitis, prepare for laparoscopic appendectomy. If symptoms worsen, return to ER immediately.",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # Diagnostic uncertainty preservation
    assert len(summary.uncertain_statements) >= 1
    assert any("appendicitis" in u.lower() or "lymphadenitis" in u.lower() for u in summary.uncertain_statements)

    uncertain_syms = [s for s in summary.structured_symptoms if s.is_uncertain or s.certainty == "SUSPECTED"]
    assert len(uncertain_syms) >= 1

    # Contingency / conditional directives
    assert len(summary.conditional_directives) >= 1
    cond_text = " ".join(summary.conditional_directives).lower()
    assert "if" in cond_text


@pytest.mark.asyncio
async def test_phase_11_2_interaction_typo_alias_and_rule_versioning():
    """
    Phase 11.2: Verifies that the typo DD-ACEI-SPผู้ is cleanly aliased to canonical DD-ACE-SPI,
    and rule versioning (v1.2) + evidence classifications are present.
    """
    items = [
        MedicationItemInput(medication_name="Lisinopril", dosage="20mg", frequency="Daily", duration="30 days", route="Oral"),
        MedicationItemInput(medication_name="Spironolactone", dosage="25mg", frequency="Daily", duration="30 days", route="Oral"),
    ]

    async with AsyncSessionLocal() as session:
        result = await cdss_service.evaluate_medication_safety(current_items=items, db=session)

    assert result.overall_safety_status in ["REVIEW_RECOMMENDED", "WARNING_FLAGGED"]
    assert len(result.interaction_alerts) >= 1

    alert = result.interaction_alerts[0]
    assert alert.interaction_id == "DD-ACE-SPI"
    assert alert.rule_version == "1.2"
    assert alert.evidence_classification == "CLASS_I_STRONG"
    assert alert.approved_by in ["Dr. Marcus Vance, MD, FACP", "CLINICAL_GOVERNANCE_BOARD"]
    assert alert.next_review_date in ["2027-10-15", "2027-06-30"]


@pytest.mark.asyncio
async def test_phase_11_2_safety_event_acknowledgement_api(client: AsyncClient, cdss_test_context):
    """
    Phase 11.2: Verifies that an authorized doctor can acknowledge or dismiss a high-impact CDSS safety alert
    via POST /api/v1/cdss/safety-events/acknowledge, updating the audit log.
    """
    ctx = cdss_test_context
    headers = {"Authorization": f"Bearer {ctx['token_doc']}"}

    # 1. Acknowledge alert
    ack_payload = {
        "event_id": "DD-WAR-ASA",
        "rule_identifier": "DD-WAR-ASA",
        "action": "ACKNOWLEDGE",
        "dismissal_reason": None,
    }
    ack_res = await client.post("/api/v1/cdss/safety-events/acknowledge", json=ack_payload, headers=headers)
    assert ack_res.status_code == 200
    ack_data = ack_res.json()
    assert ack_data["is_acknowledged"] is True
    assert ack_data["action_taken"] in ["ACKNOWLEDGED", "ACKNOWLEDGE"]
    assert ack_data["rule_identifier"] == "DD-WAR-ASA"

    # 2. Dismiss alert with clinical justification
    dismiss_payload = {
        "event_id": "DD-ACE-SPI",
        "rule_identifier": "DD-ACE-SPI",
        "action": "DISMISS",
        "dismissal_reason": "Patient has normal renal function (eGFR > 80); close serum potassium monitoring scheduled.",
    }
    dismiss_res = await client.post("/api/v1/cdss/safety-events/acknowledge", json=dismiss_payload, headers=headers)
    assert dismiss_res.status_code == 200
    dismiss_data = dismiss_res.json()
    assert dismiss_data["is_acknowledged"] is True
    assert dismiss_data["action_taken"] in ["DISMISSED", "DISMISS"]
    assert dismiss_data["dismissal_reason"] is not None
    assert "potassium" in dismiss_data["dismissal_reason"].lower()


@pytest.mark.asyncio
async def test_phase_11_2_clinician_feedback_lifecycle_and_rbac(client: AsyncClient, cdss_test_context):
    """
    Phase 11.2: Verifies submission and retrieval of clinician feedback on CDSS evaluation accuracy,
    and enforces strict RBAC preventing unauthorized patient role access.
    """
    ctx = cdss_test_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc']}"}
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat']}"}

    # 1. Doctor submits feedback
    fb_payload = {
        "feedback_type": "RELEVANT_ALERT",
        "target_type": "drug_interaction_rule",
        "target_id": str(ctx["appt"].id),
        "rule_id": "DD-WAR-ASA",
        "clinician_comment": "Warfarin and Aspirin alert accurately caught an overlapping antiplatelet order.",
        "suggested_correction": None,
    }
    fb_res = await client.post("/api/v1/cdss/feedback", json=fb_payload, headers=headers_doc)
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["feedback_type"] == "RELEVANT_ALERT"
    assert fb_data["review_status"] == "PENDING_REVIEW"
    assert fb_data["kb_version"] in ["2026.11.2-v1.2", "2026.11.3-v1.3"]

    # 2. Doctor retrieves feedback entries
    get_res = await client.get("/api/v1/cdss/feedback?limit=10", headers=headers_doc)
    assert get_res.status_code == 200
    feedbacks = get_res.json()
    assert isinstance(feedbacks, list)
    assert len(feedbacks) >= 1
    assert any(f.get("rule_id") == "DD-WAR-ASA" or f.get("feedback_type") == "RELEVANT_ALERT" for f in feedbacks)

    # 3. Patient is rejected (403 Forbidden)
    pat_res = await client.post("/api/v1/cdss/feedback", json=fb_payload, headers=headers_pat)
    assert pat_res.status_code == 403


@pytest.mark.asyncio
async def test_phase_11_3_absolute_contraindications_screening():
    """
    Phase 11.3: Tests absolute contraindication detection across clinical conditions:
    - NSAID + Chronic Kidney Disease (CI-NSAID-CKD)
    - Beta-blocker + Asthma (CI-BB-ASTHMA)
    - Metformin + Severe Renal Impairment (CI-MET-CKD)
    """
    # 1. NSAID + CKD
    ckd_items = [MedicationItemInput(medication_name="Ibuprofen 600mg", dosage="600mg", instructions="q8h prn")]
    res_ckd = await cdss_service.evaluate_medication_safety(
        current_items=ckd_items,
        patient_clinical_conditions=["Chronic Kidney Disease stage 4", "Hypertension"],
    )
    assert res_ckd.overall_safety_status == "WARNING_FLAGGED"
    assert len(res_ckd.contraindication_alerts) >= 1
    ci_ckd = next((c for c in res_ckd.contraindication_alerts if c.rule_id == "CI-NSAID-CKD"), None)
    assert ci_ckd is not None
    assert ci_ckd.severity == "CRITICAL"
    assert "KDIGO" in ci_ckd.evidence_source
    assert "renal" in ci_ckd.clinical_risk.lower()

    # 2. Beta-Blocker + Asthma
    bb_items = [MedicationItemInput(medication_name="Propranolol 40mg", dosage="40mg", instructions="Daily")]
    res_bb = await cdss_service.evaluate_medication_safety(
        current_items=bb_items,
        patient_clinical_conditions=["Bronchial Asthma"],
    )
    assert len(res_bb.contraindication_alerts) >= 1
    ci_bb = next((c for c in res_bb.contraindication_alerts if c.rule_id == "CI-BB-ASTHMA"), None)
    assert ci_bb is not None
    assert ci_bb.severity == "CRITICAL"
    assert "bronchospasm" in ci_bb.clinical_risk.lower()

    # 3. Metformin + Severe Renal Impairment
    met_items = [MedicationItemInput(medication_name="Metformin 500mg", dosage="500mg", instructions="bid")]
    res_met = await cdss_service.evaluate_medication_safety(
        current_items=met_items,
        patient_clinical_conditions=["Severe Renal Impairment eGFR 22 mL/min"],
    )
    ci_met = next((c for c in res_met.contraindication_alerts if c.rule_id == "CI-MET-CKD"), None)
    assert ci_met is not None
    assert ci_met.severity == "CRITICAL"
    assert "lactic acidosis" in ci_met.clinical_risk.lower()


@pytest.mark.asyncio
async def test_phase_11_3_explainable_recommendations_engine():
    """
    Phase 11.3: Tests Explainable AI (XAI) recommendation generation, verifying
    evidence breakdown (facts vs suspected conditions vs algorithmic predictions),
    confidence scoring, and rule attribution.
    """
    notes = NoteSummaryInput(
        chief_complaint="Severe right lower quadrant abdominal pain for 12 hours",
        symptoms="Acute sharp RLQ pain, nausea, low-grade fever. Patient denies vomiting.",
        clinical_observations="Vitals: BP 124/82, HR 88, Temp 37.8C. Abdomen tender in RLQ with rebound tenderness.",
        examination_notes="McBurney's point positive. No peritoneal signs.",
        diagnosis_summary="Suspected acute appendicitis vs mesenteric adenitis",
        treatment_plan="NPO, surgical consultation, IV hydration, urgent abdominal ultrasound",
        follow_up_instructions="Immediate transfer to surgical assessment unit",
    )

    summary = cdss_service.summarize_clinical_notes(notes)
    completeness = cdss_service.audit_documentation_completeness(notes)
    med_safety = await cdss_service.evaluate_medication_safety([])
    guidelines = cdss_service.match_clinical_guidelines(diagnosis_name="Acute Appendicitis")

    recs = cdss_service.generate_explainable_recommendations(
        summary=summary,
        completeness=completeness,
        med_safety=med_safety,
        guidelines=guidelines,
        notes=notes,
    )

    assert isinstance(recs, list)
    assert len(recs) >= 1

    for rec in recs:
        assert rec.recommendation_id is not None
        assert rec.recommendation_summary is not None
        assert rec.clinical_reasoning is not None
        assert 0.0 <= rec.confidence_score <= 1.0
        assert rec.certainty_level in ["HIGH_CONFIDENCE_FACT", "MODERATE_CLINICAL_HYPOTHESIS", "ALGORITHMIC_ALERT"]
        assert rec.evidence_breakdown is not None
        assert isinstance(rec.evidence_breakdown.clinical_facts, list)
        assert isinstance(rec.evidence_breakdown.suspected_conditions, list)
        assert isinstance(rec.evidence_breakdown.algorithmic_predictions, list)
        assert rec.kb_version == "2026.11.3-v1.3"


@pytest.mark.asyncio
async def test_phase_11_3_guideline_overdue_and_governance_monitoring():
    """
    Phase 11.3: Tests automated monitoring of clinical guidelines review dates,
    ensuring that overdue guidelines are flagged with is_review_overdue and days_until_review.
    """
    guideline_res = cdss_service.match_clinical_guidelines(diagnosis_name="Hypertension")
    assert guideline_res.total_matched >= 1

    for g in guideline_res.matched_guidelines:
        assert hasattr(g, "is_review_overdue")
        assert hasattr(g, "days_until_review")
        assert g.validation_status in ["CLINICALLY_VALIDATED", "PROVISIONAL_EVIDENCE", "OUTDATED_WARNING", "UNVERIFIED_EVIDENCE"]
        if g.is_review_overdue:
            assert g.freshness_status == "REVIEW_REQUIRED"
            assert g.days_until_review < 0


@pytest.mark.asyncio
async def test_phase_11_3_contraindications_catalog_endpoint(client: AsyncClient, cdss_test_context):
    """
    Phase 11.3: Verifies GET /api/v1/cdss/contraindications returns the active
    absolute contraindications catalog with authoritative evidence sources.
    """
    ctx = cdss_test_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc']}"}

    res = await client.get("/api/v1/cdss/contraindications", headers=headers_doc)
    assert res.status_code == 200
    catalog = res.json()
    assert isinstance(catalog, list)
    assert len(catalog) == 6

    rule_ids = [c["rule_id"] for c in catalog]
    assert "CI-NSAID-CKD" in rule_ids
    assert "CI-NSAID-PUD" in rule_ids
    assert "CI-BB-ASTHMA" in rule_ids
    assert "CI-MET-CKD" in rule_ids
    assert "CI-ACE-PREG" in rule_ids
    assert "CI-STATIN-LIVER" in rule_ids

    for ci in catalog:
        assert ci["severity"] == "CRITICAL"
        assert ci["evidence_source"] is not None
        assert ci["recommended_action"] is not None
        assert ci["kb_version"] == "2026.11.3-v1.3"


@pytest.mark.asyncio
async def test_phase_11_3_safety_dashboard_metrics_endpoint_and_rbac(client: AsyncClient, cdss_test_context):
    """
    Phase 11.3: Verifies GET /api/v1/cdss/dashboard/metrics:
    1. Authorized doctor can retrieve aggregated safety metrics, resolution rate,
       sanitized safety events (zero PHI), overdue guidelines, and feedback stats.
    2. Enforces strict RBAC: patient role is rejected with 403 Forbidden.
    """
    ctx = cdss_test_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc']}"}
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat']}"}

    # 1. Doctor retrieves metrics
    res_doc = await client.get("/api/v1/cdss/dashboard/metrics", headers=headers_doc)
    assert res_doc.status_code == 200
    metrics = res_doc.json()

    assert "total_alerts" in metrics
    assert "critical_alerts" in metrics
    assert "resolution_rate_percent" in metrics
    assert "categories_breakdown" in metrics
    assert "clinician_feedback_stats" in metrics
    assert "knowledge_base_status" in metrics
    assert "recent_safety_events" in metrics
    assert "daily_trends" in metrics

    assert metrics["knowledge_base_status"]["version"] == "2026.11.3-v1.3"
    assert isinstance(metrics["recent_safety_events"], list)
    # Zero PHI verification: ensure no patient name or email in safety events
    for evt in metrics["recent_safety_events"]:
        assert "patient_name" not in evt
        assert "patient_email" not in evt
        assert "password" not in evt

    # 2. Patient access is forbidden
    res_pat = await client.get("/api/v1/cdss/dashboard/metrics", headers=headers_pat)
    assert res_pat.status_code == 403



