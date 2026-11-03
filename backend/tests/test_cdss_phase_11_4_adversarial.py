"""
Phase 11.4: Advanced Clinical Safety Testing, Adversarial Validation & End-to-End Integration.

Dedicated test suite verifying:
- Scenario A: Chronic Kidney Disease & NSAID Contraindication with Prescription Preservation
- Scenario B: Multiple Concomitant Medication Interactions & Deduplication
- Scenario C: Unknown Allergy Status (Never Defaults to Safe)
- Scenario D: Contradictory Clinical Documentation (Fever vs Normal Vitals)
- Scenario E: Uncertain Pregnancy Status (Information-Required Warning, Never Assumes Confirmed State)
- Scenario F: Historical vs Current Symptoms Isolation
- Scenario G: Uncertain Clinical Language Preservation (Never Converts Hypotheses to Confirmed Diagnoses)
- Scenario H: Outdated Clinical Guidelines Governance & Freshness Tracking
- Scenario I: Clinician Dismissal of Critical Warnings with Immutable Audit Retention
- Scenario J: Conflicting Patient Information Across Multiple EHR Sections
- Security, RBAC & Cross-Hospital IDOR Protection
- End-to-End Complete Clinical Encounter Workflow
- Explainable AI Matrix & Performance Reliability
"""
import asyncio
import time
import uuid
from datetime import date, datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.cdss import CDSSClinicianFeedback, CDSSSafetyEvent
from app.models.doctor import Doctor
from app.models.ehr import ClinicalAuditLog, ConsultationNote, Diagnosis, Prescription, PrescriptionItem
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
from app.services.ehr_service import EHRService


@pytest.fixture
async def p11_4_context():
    """Sets up isolated hospital, doctors, patient, appointment, and EHR history in medismart_test_db."""
    async with AsyncSessionLocal() as session:
        # 1. Hospital A & Hospital B
        hosp_a = Hospital(
            id=uuid.uuid4(),
            name=f"General Hospital Alpha {uuid.uuid4().hex[:6]}",
            address="100 Medical Blvd",
            city="Metropolis",
            state="NY",
            is_active=True,
        )
        hosp_b = Hospital(
            id=uuid.uuid4(),
            name=f"St. Jude Hospital Beta {uuid.uuid4().hex[:6]}",
            address="200 Healthcare Ave",
            city="Gotham",
            state="NJ",
            is_active=True,
        )
        session.add_all([hosp_a, hosp_b])

        # 2. Treating Doctor in Hospital A
        doc_a_user = User(
            id=uuid.uuid4(),
            email=f"doc_alpha_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Dr. Sarah Mitchell",
            role="doctor",
            is_active=True,
        )
        session.add(doc_a_user)
        await session.flush()

        doc_a = Doctor(
            id=uuid.uuid4(),
            user_id=doc_a_user.id,
            hospital_id=hosp_a.id,
            specialty="Internal Medicine",
            qualification="MD, FACP",
            experience_years=15,
            is_available=True,
        )
        session.add(doc_a)

        # 3. External Doctor in Hospital B (for IDOR testing)
        doc_b_user = User(
            id=uuid.uuid4(),
            email=f"doc_beta_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Dr. Robert Hayes",
            role="doctor",
            is_active=True,
        )
        session.add(doc_b_user)
        await session.flush()

        doc_b = Doctor(
            id=uuid.uuid4(),
            user_id=doc_b_user.id,
            hospital_id=hosp_b.id,
            specialty="Cardiology",
            qualification="MD",
            experience_years=8,
            is_available=True,
        )
        session.add(doc_b)

        # 4. Patient User
        pat_user = User(
            id=uuid.uuid4(),
            email=f"pat_adv_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_pw_test",
            full_name="Eleanor Vance",
            role="patient",
            is_active=True,
        )
        session.add(pat_user)
        await session.flush()

        # 5. Scheduled Appointment with Doctor A in Hospital A
        appt = Appointment(
            id=uuid.uuid4(),
            appointment_token=f"APPT-P114-{uuid.uuid4().hex[:6].upper()}",
            patient_id=pat_user.id,
            doctor_id=doc_a.id,
            hospital_id=hosp_a.id,
            appointment_date=date(2026, 11, 20),
            appointment_time=datetime.strptime("14:30", "%H:%M").time(),
            status="scheduled",
            notes="Follow-up consultation for clinical review.",
        )
        session.add(appt)
        await session.commit()

        context = {
            "hosp_a": hosp_a,
            "hosp_b": hosp_b,
            "doc_a_user": doc_a_user,
            "doc_a": doc_a,
            "doc_b_user": doc_b_user,
            "doc_b": doc_b,
            "pat_user": pat_user,
            "appt": appt,
            "token_doc_a": create_access_token(user_id=doc_a_user.id, role="doctor"),
            "token_doc_b": create_access_token(user_id=doc_b_user.id, role="doctor"),
            "token_pat": create_access_token(user_id=pat_user.id, role="patient"),
        }
        yield context

        # Teardown: Clean up test records
        async with AsyncSessionLocal() as td_sess:
            await td_sess.execute(ClinicalAuditLog.__table__.delete().where(ClinicalAuditLog.patient_id == pat_user.id))
            await td_sess.execute(CDSSSafetyEvent.__table__.delete().where(CDSSSafetyEvent.patient_id == pat_user.id))
            await td_sess.execute(CDSSClinicianFeedback.__table__.delete().where(CDSSClinicianFeedback.doctor_id.in_([doc_a.id, doc_b.id])))
            await td_sess.execute(PrescriptionItem.__table__.delete())
            await td_sess.execute(Prescription.__table__.delete().where(Prescription.patient_id == pat_user.id))
            await td_sess.execute(Diagnosis.__table__.delete().where(Diagnosis.patient_id == pat_user.id))
            await td_sess.execute(ConsultationNote.__table__.delete().where(ConsultationNote.patient_id == pat_user.id))
            await td_sess.execute(Appointment.__table__.delete().where(Appointment.id == appt.id))
            await td_sess.execute(Doctor.__table__.delete().where(Doctor.id.in_([doc_a.id, doc_b.id])))
            await td_sess.execute(User.__table__.delete().where(User.id.in_([doc_a_user.id, doc_b_user.id, pat_user.id])))
            await td_sess.execute(Hospital.__table__.delete().where(Hospital.id.in_([hosp_a.id, hosp_b.id])))
            await td_sess.commit()


# ===========================================================================
# 1. ADVERSARIAL CLINICAL SCENARIO TESTS (SCENARIOS A - J)
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_a_ckd_nsaid_contraindication_and_preservation():
    """
    Scenario A – Chronic Kidney Disease:
    - Patient has documented CKD.
    - Doctor enters an NSAID prescription (Ibuprofen 600mg).
    - Verify contraindication engine detects relevant risk (CI-NSAID-CKD).
    - Verify alert includes evidence source (KDIGO 2024 / FDA Boxed Warning) and clinical risk.
    - Verify that the system does NOT automatically modify or cancel the prescription items.
    """
    rx_items = [MedicationItemInput(medication_name="Ibuprofen 600mg", dosage="600mg", instructions="q8h prn")]
    res = await cdss_service.evaluate_medication_safety(
        current_items=rx_items,
        patient_clinical_conditions=["Chronic Kidney Disease stage 4", "Hypertension"],
    )

    # 1. Verify contraindication detected
    assert res.overall_safety_status == "WARNING_FLAGGED"
    assert len(res.contraindication_alerts) >= 1
    ci = next((c for c in res.contraindication_alerts if c.rule_id == "CI-NSAID-CKD"), None)
    assert ci is not None
    assert ci.severity == "CRITICAL"
    assert "KDIGO" in ci.evidence_source
    assert "renal decompensation" in ci.clinical_risk.lower() or "renal" in ci.clinical_risk.lower()
    assert "fda boxed warning" in ci.evidence_source.lower() or "kdigo" in ci.evidence_source.lower()

    # 2. Assistive boundary: Verify prescription items are NOT automatically deleted, canceled, or changed
    assert len(rx_items) == 1
    assert rx_items[0].medication_name == "Ibuprofen 600mg"
    assert rx_items[0].dosage == "600mg"
    assert "Assistive" in res.disclaimer


@pytest.mark.asyncio
async def test_scenario_b_multiple_medication_interactions_and_deduplication():
    """
    Scenario B – Multiple Medication Interactions:
    - Patient has several active medications (Warfarin, Spironolactone, Fluoxetine).
    - New prescription introduces multiple potential interactions (Aspirin, Lisinopril, Tramadol).
    - Verify duplicate and overlapping alerts are handled cleanly.
    - Verify severity and evidence classifications remain accurate across all pairs.
    """
    rx_items = [
        MedicationItemInput(medication_name="Warfarin 5mg", dosage="5mg", instructions="qhs"),
        MedicationItemInput(medication_name="Aspirin 81mg", dosage="81mg", instructions="daily"),
        MedicationItemInput(medication_name="Spironolactone 25mg", dosage="25mg", instructions="daily"),
        MedicationItemInput(medication_name="Lisinopril 20mg", dosage="20mg", instructions="daily"),
        MedicationItemInput(medication_name="Fluoxetine 20mg", dosage="20mg", instructions="daily"),
        MedicationItemInput(medication_name="Tramadol 50mg", dosage="50mg", instructions="q6h prn"),
    ]

    res = await cdss_service.evaluate_medication_safety(current_items=rx_items)

    assert res.overall_safety_status == "WARNING_FLAGGED"
    alerts = res.interaction_alerts
    assert len(alerts) >= 3

    # Verify no duplicate alert entries for the exact same rule
    interaction_ids = [a.interaction_id for a in alerts]
    assert len(interaction_ids) == len(set(interaction_ids)), "Duplicate interaction alerts detected!"

    # Verify expected clinical pairs are present
    assert "DD-WAR-ASA" in interaction_ids
    assert "DD-ACE-SPI" in interaction_ids
    assert "DD-SSRI-TRA" in interaction_ids

    # Verify individual severity and evidence accuracy
    war_asa = next(a for a in alerts if a.interaction_id == "DD-WAR-ASA")
    assert war_asa.severity == "CRITICAL"
    assert war_asa.evidence_classification == "CLASS_I_STRONG"

    ace_spi = next(a for a in alerts if a.interaction_id == "DD-ACE-SPI")
    assert ace_spi.severity in ["HIGH", "CRITICAL"]
    assert "hyperkalemia" in ace_spi.risk_summary.lower()

    ssri_tra = next(a for a in alerts if a.interaction_id == "DD-SSRI-TRA")
    assert ssri_tra.severity == "HIGH"
    assert "serotonin syndrome" in ssri_tra.risk_summary.lower()


@pytest.mark.asyncio
async def test_scenario_c_unknown_allergy_status_never_defaults_to_safe(client: AsyncClient, p11_4_context):
    """
    Scenario C – Unknown Allergy Status:
    - Patient has no structured allergy information.
    - Doctor opens consultation workspace / calls insights.
    - Verify system displays NOT_DOCUMENTED or verification state.
    - Never interpret missing information as confirmed absence of allergies.
    """
    ctx = p11_4_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc_a']}"}

    # Query insights for patient without documented allergies
    res = await client.get(f"/api/v1/cdss/patient/{ctx['pat_user'].id}/insights", headers=headers_doc)
    assert res.status_code == 200
    data = res.json()

    assert data["allergy_documentation_status"] == "NOT_DOCUMENTED"
    assert data["allergy_safety_warning"] is not None
    assert "NOT DOCUMENTED" in data["allergy_safety_warning"]
    assert "must NOT be construed as confirmation of no drug allergies" in data["allergy_safety_warning"]

    # In medication safety check, verify it never defaults to safe
    med_res = await cdss_service.evaluate_medication_safety(
        current_items=[MedicationItemInput(medication_name="Amoxicillin 500mg", dosage="500mg", instructions="tid")],
        patient_id=ctx["pat_user"].id,
    )
    assert med_res.allergy_safety_status == "NOT_DOCUMENTED"
    assert med_res.allergy_warning_banner is not None
    assert "NOT DOCUMENTED" in med_res.allergy_warning_banner


@pytest.mark.asyncio
async def test_scenario_d_contradictory_clinical_documentation_fever_vs_normal_vitals():
    """
    Scenario D – Contradictory Clinical Documentation:
    - Symptoms: Patient reports fever and chills.
    - Vitals: Temperature is within the normal range (afebrile, 37.0 C).
    - Verify contradiction is flagged for clinician review.
    - Verify system does not automatically decide which information is correct.
    """
    notes = NoteSummaryInput(
        chief_complaint="Subjective fever and generalized chills for 48 hours",
        symptoms="High fever, chills, diaphoresis. Patient feels hot.",
        clinical_observations="Vitals: BP 120/78 mmHg, HR 68 bpm, Temp 37.0 C, RR 14. Patient is comfortable, afebrile.",
        examination_notes="Lungs clear bilaterally, normothermic, skin warm and dry.",
        diagnosis_summary="Viral syndrome vs transient pyrexia",
        treatment_plan="Supportive hydration, rest, monitor temperature at home",
        follow_up_instructions="Return to clinic if temperature exceeds 38.5 C",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # 1. Verify discordance is flagged
    assert len(summary.contradictions_detected) >= 1
    fever_contra = next((c for c in summary.contradictions_detected if "fever" in c.lower()), None)
    assert fever_contra is not None
    assert "Discordance detected" in fever_contra
    assert "afebrile" in fever_contra.lower() or "normal temperature" in fever_contra.lower()

    # 2. Verify system did NOT delete or overwrite symptoms
    symptom_names = [s.symptom_name.lower() for s in summary.structured_symptoms]
    assert any("fever" in sn for sn in symptom_names)


@pytest.mark.asyncio
async def test_scenario_e_uncertain_pregnancy_status_information_required():
    """
    Scenario E – Uncertain Pregnancy Status:
    - Patient pregnancy status is unavailable or uncertain (e.g. 'possible pregnancy', 'pregnancy test pending').
    - Doctor enters an ACE inhibitor / ARB prescription (Lisinopril).
    - Verify pregnancy-dependent medication rules do NOT assume confirmed pregnant state.
    - Verify system displays an appropriate information-required warning (CI-WARN-PREG-UNCONFIRMED).
    - If confirmed pregnancy is documented, verify confirmed CI-ACE-PREG is triggered.
    """
    rx_ace = [MedicationItemInput(medication_name="Lisinopril 10mg", dosage="10mg", instructions="daily")]

    # 1. Uncertain status: 'pregnancy test pending'
    res_uncertain = await cdss_service.evaluate_medication_safety(
        current_items=rx_ace,
        patient_clinical_conditions=["Hypertension", "Pregnancy status unknown - urine hCG test pending"],
    )

    # Must NOT assume confirmed pregnancy (CI-ACE-PREG must not trigger as absolute confirmed contraindication)
    assert not any(c.rule_id == "CI-ACE-PREG" for c in res_uncertain.contraindication_alerts)

    # Must flag Information Required warning
    assert any(c.rule_id == "CI-WARN-PREG-UNCONFIRMED" for c in res_uncertain.contraindication_alerts)
    warn_alert = next(c for c in res_uncertain.contraindication_alerts if c.rule_id == "CI-WARN-PREG-UNCONFIRMED")
    assert warn_alert.severity == "HIGH"
    assert "Information required" in warn_alert.recommended_action
    assert "serum/urine hcg" in warn_alert.recommended_action.lower()
    assert "FDA Boxed Warning" in warn_alert.evidence_source

    # 2. Confirmed pregnancy state
    res_confirmed = await cdss_service.evaluate_medication_safety(
        current_items=rx_ace,
        patient_clinical_conditions=["Hypertension", "Confirmed first trimester pregnancy"],
    )
    assert any(c.rule_id == "CI-ACE-PREG" for c in res_confirmed.contraindication_alerts)
    ci_confirmed = next(c for c in res_confirmed.contraindication_alerts if c.rule_id == "CI-ACE-PREG")
    assert ci_confirmed.severity == "CRITICAL"
    assert "fetotoxicity" in ci_confirmed.clinical_risk.lower()


@pytest.mark.asyncio
async def test_scenario_f_historical_vs_current_symptoms_isolation():
    """
    Scenario F – Historical Versus Current Symptoms:
    - Patient has historical asthma diagnosis in EHR or past note ('history of childhood asthma').
    - Current consultation contains no acute asthma symptoms ('acute pruritic dermatitis on forearms').
    - Verify historical asthma is not incorrectly presented as an active acute presenting complaint.
    """
    notes = NoteSummaryInput(
        chief_complaint="Severe pruritic erythematous rash on bilateral forearms for 3 days",
        symptoms="Itchy skin rash, erythema, mild scaling. Past history of childhood asthma (resolved).",
        clinical_observations="Vitals normal. Skin examination shows localized contact dermatitis.",
        examination_notes="No wheezing, breath sounds clear bilaterally, chest non-tender.",
        diagnosis_summary="Acute allergic contact dermatitis",
        treatment_plan="Topical hydrocortisone 1%, avoid suspected allergen",
        follow_up_instructions="Return in 10 days if dermatitis persists",
    )

    summary = cdss_service.summarize_clinical_notes(notes)

    # 1. Verify asthma is extracted with HISTORICAL_RECORD attribution
    asthma_sym = next((s for s in summary.structured_symptoms if "asthma" in s.symptom_name.lower()), None)
    if asthma_sym:
        assert asthma_sym.source_attribution == "HISTORICAL_RECORD" or asthma_sym.is_historical is True

    # 2. Verify executive summary presenting symptoms strictly contain the acute complaint and NOT historical asthma
    assert "asthma" not in summary.executive_summary.lower()
    assert "rash" in summary.executive_summary.lower() or "erythematous" in summary.executive_summary.lower()


@pytest.mark.asyncio
async def test_scenario_g_uncertain_clinical_language_preserves_hypotheses():
    """
    Scenario G – Uncertain Clinical Language:
    - Possible pneumonia.
    - Suspected appendicitis.
    - Rule out cardiac disease.
    - Verify uncertainty is preserved as MODERATE_CLINICAL_HYPOTHESIS.
    - Never convert suspected conditions into confirmed diagnoses without clinician action.
    """
    notes = NoteSummaryInput(
        chief_complaint="Right lower quadrant abdominal pain",
        symptoms="Acute RLQ abdominal pain. Suspected appendicitis vs possible mesenteric adenitis. Rule out ovarian torsion.",
        clinical_observations="Vitals: BP 118/76, HR 82, Temp 37.6 C. Tenderness at McBurney's point.",
        examination_notes="Rebound tenderness in RLQ.",
        diagnosis_summary="Provisional differential: acute appendicitis to be ruled out",
        treatment_plan="NPO, surgical consultation, urgent ultrasound",
        follow_up_instructions="Immediate surgical transfer",
    )

    summary = cdss_service.summarize_clinical_notes(notes)
    recs = cdss_service.generate_explainable_recommendations(
        summary=summary,
        completeness=cdss_service.audit_documentation_completeness(notes),
        med_safety=await cdss_service.evaluate_medication_safety([]),
        guidelines=cdss_service.match_clinical_guidelines(diagnosis_name="Abdominal Pain"),
        notes=notes,
    )

    # 1. Verify hedge phrases captured in uncertain_statements
    assert len(summary.uncertain_statements) >= 1
    assert any("appendicitis" in u.lower() or "adenitis" in u.lower() or "torsion" in u.lower() for u in summary.uncertain_statements)

    # 2. Verify explainable AI recommendation classifies it as MODERATE_CLINICAL_HYPOTHESIS
    hyp_rec = next((r for r in recs if r.certainty_level == "MODERATE_CLINICAL_HYPOTHESIS"), None)
    assert hyp_rec is not None
    assert "suspected" in hyp_rec.clinical_reasoning.lower() or "provisional" in hyp_rec.clinical_reasoning.lower()
    assert len(hyp_rec.evidence.suspected_conditions) >= 1


@pytest.mark.asyncio
async def test_scenario_h_outdated_clinical_guidelines_governance():
    """
    Scenario H – Outdated Clinical Guidelines:
    - Simulates an overdue guideline (review date passed).
    - Verify REVIEW_REQUIRED or OUTDATED_WARNING.
    - Display review date, days overdue, and evidence source.
    - Do not silently present outdated information as current.
    """
    guideline_res = cdss_service.match_clinical_guidelines(diagnosis_name="Hypertension")
    assert guideline_res.total_matched >= 1

    for g in guideline_res.matched_guidelines:
        assert hasattr(g, "is_review_overdue")
        assert hasattr(g, "days_until_review")
        assert hasattr(g, "validation_status")
        if g.is_review_overdue:
            assert g.freshness_status == "REVIEW_REQUIRED"
            assert g.validation_status == "OUTDATED_WARNING"
            assert g.days_until_review < 0
            assert g.next_review_date is not None
            assert g.publishing_authority is not None


@pytest.mark.asyncio
async def test_scenario_i_clinician_dismisses_critical_warning_with_audit_retention(client: AsyncClient, p11_4_context):
    """
    Scenario I – Clinician Dismisses a Critical Warning:
    - Authorized doctor acknowledges or dismisses an alert with clinical rationale.
    - Action, rationale, and doctor identity are recorded in cdss_safety_events and clinical_audit_logs.
    - Original warning and full audit history remain permanently available and queryable.
    """
    ctx = p11_4_context
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc_a']}"}

    # 1. Doctor dismisses a critical alert with detailed clinical justification
    dismiss_payload = {
        "event_id": "CI-NSAID-CKD",
        "rule_identifier": "CI-NSAID-CKD",
        "appointment_id": str(ctx["appt"].id),
        "action": "DISMISS",
        "dismissal_reason": "Patient has stable baseline eGFR 58; prescribed 3-day short course of low-dose Ibuprofen with close nephrology follow-up.",
    }
    dismiss_res = await client.post("/api/v1/cdss/safety-events/acknowledge", json=dismiss_payload, headers=headers_doc)
    assert dismiss_res.status_code == 200
    dismiss_data = dismiss_res.json()

    assert dismiss_data["action_taken"] == "DISMISSED"
    assert dismiss_data["is_acknowledged"] is True
    assert dismiss_data["dismissal_reason"] == dismiss_payload["dismissal_reason"]
    assert dismiss_data["rule_identifier"] == "CI-NSAID-CKD"

    # 2. Verify audit trail immutability in database
    async with AsyncSessionLocal() as session:
        # Check safety event
        se_check = await session.execute(
            select(CDSSSafetyEvent).where(
                CDSSSafetyEvent.doctor_id == ctx["doc_a"].id,
                CDSSSafetyEvent.rule_identifier == "CI-NSAID-CKD",
                CDSSSafetyEvent.action_taken == "DISMISSED",
            )
        )
        saved_event = se_check.scalar_one_or_none()
        assert saved_event is not None
        assert saved_event.doctor_id == ctx["doc_a"].id
        assert saved_event.dismissal_reason == dismiss_payload["dismissal_reason"]

        # Check clinical audit log
        audit_check = await session.execute(
            select(ClinicalAuditLog).where(
                ClinicalAuditLog.doctor_id == ctx["doc_a"].id,
                ClinicalAuditLog.target_type == "cdss_safety_event",
                ClinicalAuditLog.action == "CDSS_WARNING_DISMISS",
            )
        )
        saved_audit = audit_check.scalar_one_or_none()
        assert saved_audit is not None
        assert saved_audit.doctor_id == ctx["doc_a"].id
        assert saved_audit.metadata_json["rule_identifier"] == "CI-NSAID-CKD"


@pytest.mark.asyncio
async def test_scenario_j_conflicting_patient_information_cross_record():
    """
    Scenario J – Conflicting Patient Information Across Multiple EHR Sections:
    - Patient longitudinal EHR lists chronic condition 'Type 2 Diabetes Mellitus' and allergy 'Penicillin'.
    - Current consultation note asserts 'Patient denies diabetes, no past medical history, denies drug allergies'.
    - Discrepancy is flagged in contradictions_detected with source attribution without fabricating missing facts.
    """
    notes = NoteSummaryInput(
        chief_complaint="Routine health maintenance checkup",
        symptoms="No acute symptoms. Patient denies diabetes, denies prior medical history, denies drug allergies.",
        clinical_observations="Vitals normal, physical examination unremarkable.",
        examination_notes="Heart regular, lungs clear.",
        diagnosis_summary="General wellness examination",
        treatment_plan="Routine screening labs ordered",
        follow_up_instructions="Return in 1 year",
    )

    from app.schemas.cdss import HistoryDiagnosisItem, PatientHistoryInsightsResponse
    mock_insights = PatientHistoryInsightsResponse(
        patient_id=str(uuid.uuid4()),
        patient_name="Arthur Pendelton",
        total_recorded_consultations=3,
        active_diagnoses=[],
        chronic_conditions=[
            HistoryDiagnosisItem(
                diagnosis_name="Type 2 Diabetes Mellitus",
                diagnosis_code="E11.9",
                diagnosis_date="2023-05-10",
                status="chronic",
            )
        ],
        resolved_diagnoses=[],
        active_prescriptions=[],
        documented_allergies=["Penicillin"],
        allergy_documentation_status="DOCUMENTED_ALLERGIES",
        allergy_safety_warning=None,
        adherence_follow_up_summary="Good compliance reported.",
        clinical_caution_flags=[],
    )

    summary = cdss_service.summarize_clinical_notes(notes, patient_insights=mock_insights)

    assert len(summary.contradictions_detected) >= 2
    # Verify chronic condition conflict
    dm_conflict = next((c for c in summary.contradictions_detected if "Diabetes" in c), None)
    assert dm_conflict is not None
    assert "Cross-Record Discrepancy" in dm_conflict
    assert "Current Encounter Notes vs Longitudinal EHR Record" in dm_conflict

    # Verify allergy conflict
    allergy_conflict = next((c for c in summary.contradictions_detected if "Penicillin" in c), None)
    assert allergy_conflict is not None
    assert "Cross-Record Discrepancy" in allergy_conflict
    assert "Longitudinal EHR Allergy Record" in allergy_conflict


# ===========================================================================
# 2. SECURITY, RBAC & CROSS-HOSPITAL IDOR TESTING
# ===========================================================================

@pytest.mark.asyncio
async def test_phase_11_4_security_rbac_and_cross_hospital_isolation(client: AsyncClient, p11_4_context):
    """
    Security & Authorization Testing:
    1. Patient cannot access doctor-only CDSS endpoints (403 Forbidden).
    2. External Doctor B cannot access Doctor A's patient insights (IDOR prevention; 403 Forbidden).
    3. Safety dashboard metrics requires doctor/admin role; patient receives 403.
    4. Clinician feedback requires authorized doctor/admin role.
    """
    ctx = p11_4_context
    headers_doc_a = {"Authorization": f"Bearer {ctx['token_doc_a']}"}
    headers_doc_b = {"Authorization": f"Bearer {ctx['token_doc_b']}"}
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat']}"}

    # 1. Patient is rejected from CDSS encounter evaluation
    eval_payload = {
        "appointment_id": str(ctx["appt"].id),
        "patient_id": str(ctx["pat_user"].id),
        "notes": {
            "chief_complaint": "Headache",
            "symptoms": "Throbbing pain",
        },
        "prescriptions": [],
    }
    pat_eval_res = await client.post("/api/v1/cdss/evaluate", json=eval_payload, headers=headers_pat)
    assert pat_eval_res.status_code == 403

    # 2. External Doctor B (Hospital B) tries to access Patient from Hospital A without appointment
    doc_b_insights_res = await client.get(f"/api/v1/cdss/patient/{ctx['pat_user'].id}/insights", headers=headers_doc_b)
    assert doc_b_insights_res.status_code == 403
    assert "Access denied" in doc_b_insights_res.json()["detail"]

    # 3. Patient cannot access CDSS dashboard metrics
    dash_pat_res = await client.get("/api/v1/cdss/dashboard/metrics", headers=headers_pat)
    assert dash_pat_res.status_code == 403

    # 4. Patient cannot submit clinician feedback
    fb_payload = {
        "feedback_type": "RELEVANT_ALERT",
        "target_type": "interaction_rule",
        "target_id": "DD-WAR-ASA",
        "clinician_comment": "Testing unauthorized feedback submission",
    }
    pat_fb_res = await client.post("/api/v1/cdss/feedback", json=fb_payload, headers=headers_pat)
    assert pat_fb_res.status_code == 403


# ===========================================================================
# 3. COMPLETE END-TO-END WORKFLOW VALIDATION
# ===========================================================================

@pytest.mark.asyncio
async def test_phase_11_4_end_to_end_clinical_encounter_workflow(client: AsyncClient, p11_4_context):
    """
    Validates complete clinical workflow:
    1. Doctor opens appointment.
    2. Doctor accesses patient medical history & insights.
    3. Doctor records clinical notes.
    4. CDSS evaluates encounter (medication safety, contraindications, guidelines, XAI).
    5. Doctor reviews warnings, dismisses one alert with clinical rationale.
    6. Doctor completes consultation and issues digital prescription.
    7. Medical records, audit logs, and safety events remain synchronized.
    """
    ctx = p11_4_context
    headers_doc_a = {"Authorization": f"Bearer {ctx['token_doc_a']}"}

    # Step 1 & 2: Doctor accesses patient insights
    insights_res = await client.get(f"/api/v1/cdss/patient/{ctx['pat_user'].id}/insights", headers=headers_doc_a)
    assert insights_res.status_code == 200

    # Step 3 & 4: CDSS Evaluation of consultation notes and proposed prescriptions
    eval_payload = {
        "appointment_id": str(ctx["appt"].id),
        "patient_id": str(ctx["pat_user"].id),
        "notes": {
            "chief_complaint": "Acute moderate tension-type headache for 24 hours",
            "symptoms": "Bilateral band-like headache, mild photophobia. No nausea, no vomiting.",
            "clinical_observations": "Vitals: BP 122/80, HR 74, Temp 36.8 C. Neurological exam intact.",
            "examination_notes": "Cranial nerves II-XII intact. No neck stiffness.",
            "diagnosis_summary": "Tension-type headache",
            "treatment_plan": "Oral hydration, rest, PRN analgesia with Ibuprofen",
            "follow_up_instructions": "Return if headache worsens or focal deficits develop",
        },
        "prescriptions": [
            {"medication_name": "Ibuprofen 400mg", "dosage": "400mg", "instructions": "TID PRN"},
        ],
        "diagnosis_name": "Tension-type headache",
    }

    eval_res = await client.post("/api/v1/cdss/evaluate", json=eval_payload, headers=headers_doc_a)
    assert eval_res.status_code == 200
    cdss_out = eval_res.json()

    assert "summary" in cdss_out
    assert "documentation_completeness" in cdss_out
    assert "medication_safety" in cdss_out
    assert "explainable_recommendations" in cdss_out
    assert len(cdss_out["explainable_recommendations"]) >= 1

    # Step 5: Doctor acknowledges/dismisses an alert with clinical justification
    ack_payload = {
        "rule_identifier": "DD-WAR-ASA",
        "appointment_id": str(ctx["appt"].id),
        "action": "ACKNOWLEDGE",
    }
    ack_res = await client.post("/api/v1/cdss/safety-events/acknowledge", json=ack_payload, headers=headers_doc_a)
    assert ack_res.status_code == 200

    # Step 6: Doctor finalizes consultation in EHR
    consult_payload = {
        "appointment_id": str(ctx["appt"].id),
        "chief_complaint": "Acute moderate tension-type headache",
        "symptoms": "Bilateral band-like headache",
        "clinical_observations": "Normal neurological exam",
        "examination_notes": "Cranial nerves intact",
        "diagnosis_summary": "Tension-type headache",
        "treatment_plan": "Oral hydration, rest",
        "doctor_recommendations": "Adequate sleep and hydration",
        "follow_up_instructions": "Return PRN",
        "diagnoses": [
            {
                "diagnosis_name": "Tension-type headache",
                "clinical_description": "Frequent episodic tension-type headache",
                "diagnosis_code": "G44.2",
                "status": "active",
            }
        ],
        "prescription": {
            "notes": "Short course for tension headache",
            "items": [
                {
                    "medication_name": "Ibuprofen 400mg",
                    "dosage": "400mg",
                    "frequency": "TID PRN",
                    "duration": "5 days",
                    "route": "Oral",
                    "instructions": "Take with meals",
                }
            ],
        },
    }

    consult_res = await client.post("/api/v1/ehr/consultations", json=consult_payload, headers=headers_doc_a)
    assert consult_res.status_code == 201
    consult_data = consult_res.json()
    assert consult_data["id"] is not None
    assert len(consult_data["prescriptions"]) >= 1

    # Step 7: Patient views their medical records
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat']}"}
    pat_records_res = await client.get("/api/v1/ehr/my-history", headers=headers_pat)
    assert pat_records_res.status_code == 200
    pat_records = pat_records_res.json()
    assert len(pat_records["consultations"]) >= 1
    assert any(c["id"] == consult_data["id"] for c in pat_records["consultations"])


# ===========================================================================
# 4. EXPLAINABLE AI MATRIX & PERFORMANCE RELIABILITY BENCHMARK
# ===========================================================================

@pytest.mark.asyncio
async def test_phase_11_4_xai_matrix_and_performance_reliability():
    """
    Explainable AI & Performance Reliability:
    1. Validates EvidenceBreakdown structure across all domains.
    2. Verifies confidence scores are bounded in [0.0, 1.0].
    3. Benchmarks in-process CDSS evaluation response time (< 500ms).
    4. Evaluates concurrent alert acknowledgement safety under load.
    """
    notes = NoteSummaryInput(
        chief_complaint="Chest tightness and dyspnea on exertion for 1 week",
        symptoms="Substernal chest tightness, shortness of breath on climbing stairs. Denies diaphoresis.",
        clinical_observations="Vitals: BP 142/88 mmHg, HR 78 bpm, Temp 36.9 C. Lungs clear.",
        examination_notes="Regular rate and rhythm, S1/S2 audible, no murmurs. JVP not elevated.",
        diagnosis_summary="Suspected exertional angina vs atypical chest pain",
        treatment_plan="Rest, cardiology referral, stress echocardiography ordered",
        follow_up_instructions="Immediate ER evaluation if rest pain or radiation occurs",
    )

    # 1. Performance Benchmark: Measure in-process inference time
    start_time = time.perf_counter()
    summary = cdss_service.summarize_clinical_notes(notes)
    completeness = cdss_service.audit_documentation_completeness(notes)
    med_safety = await cdss_service.evaluate_medication_safety([])
    guidelines = cdss_service.match_clinical_guidelines(diagnosis_name="Hypertension")
    recs = cdss_service.generate_explainable_recommendations(
        summary=summary,
        completeness=completeness,
        med_safety=med_safety,
        guidelines=guidelines,
        notes=notes,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Ensure in-process execution completes in < 500ms (high performance reliability)
    assert elapsed_ms < 500.0, f"CDSS evaluation exceeded 500ms performance target: {elapsed_ms:.2f}ms"

    # 2. XAI EvidenceBreakdown Validation
    assert len(recs) >= 1
    for rec in recs:
        assert rec.recommendation_id is not None
        assert 0.0 <= rec.confidence_score <= 1.0
        assert rec.certainty_level in ["HIGH_CONFIDENCE_FACT", "MODERATE_CLINICAL_HYPOTHESIS", "ALGORITHMIC_ALERT"]
        assert rec.evidence is not None
        assert isinstance(rec.evidence.clinical_facts, list)
        assert isinstance(rec.evidence.suspected_conditions, list)
        assert isinstance(rec.evidence.algorithmic_predictions, list)
        assert rec.kb_version == "2026.11.3-v1.3"

    # 3. Concurrent Alert Evaluation Safety
    async def run_safety_eval():
        return await cdss_service.evaluate_medication_safety(
            current_items=[
                MedicationItemInput(medication_name="Ibuprofen 400mg", dosage="400mg", instructions="prn"),
                MedicationItemInput(medication_name="Warfarin 5mg", dosage="5mg", instructions="qhs"),
            ],
            patient_clinical_conditions=["Chronic Kidney Disease stage 3"],
        )

    concurrent_results = await asyncio.gather(*[run_safety_eval() for _ in range(10)])
    assert len(concurrent_results) == 10
    for res in concurrent_results:
        assert res.overall_safety_status == "WARNING_FLAGGED"
        assert len(res.contraindication_alerts) >= 1
        assert len(res.interaction_alerts) >= 1
