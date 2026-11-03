"""
Test Suite for AI Medical Report Analysis & Intelligent Health Document Understanding.
Validates Phase 12.0 requirements across Document Processing, OCR Fallback,
Parameter Extraction, Range Analysis, Historical Comparison, RBAC/IDOR Security, and Audit Integrity.
"""
import io
import uuid
from datetime import date, datetime
from typing import List

import pymupdf
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.ehr import ClinicalAuditLog
from app.models.hospital import Hospital
from app.models.medical_report import (
    ExtractedMedicalParameter,
    MedicalDocument,
    MedicalParameterCorrection,
    MedicalReportAnalysis,
    MedicalReportReview,
)
from app.models.user import User
from app.services.medical_report_service import medical_report_service


def create_sample_digital_pdf(text_lines: List[str]) -> bytes:
    """Creates a synthetic digital PDF in memory with selectable text."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 50
    for line in text_lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 22
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_sample_scanned_pdf(text_lines: List[str]) -> bytes:
    """
    Creates a synthetic scanned PDF (pure raster image with zero digital text layer)
    to verify RapidOCR fallback.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60
    for line in text_lines:
        page.insert_text((50, y), line, fontsize=14)
        y += 30
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    doc.close()

    scanned_doc = pymupdf.open()
    scanned_page = scanned_doc.new_page(width=pix.width, height=pix.height)
    scanned_page.insert_image(scanned_page.rect, stream=img_bytes)
    scanned_bytes = scanned_doc.tobytes()
    scanned_doc.close()
    return scanned_bytes


@pytest.fixture
async def p12_context():
    """Sets up clean hospital, doctors, patients, and appointment relations for testing."""
    async with AsyncSessionLocal() as session:
        # 1. Hospital A & B
        hosp_a = Hospital(
            id=uuid.uuid4(),
            name=f"Metro General Health {uuid.uuid4().hex[:6]}",
            address="100 Metro Blvd",
            city="Metropolis",
            state="NY",
            email=f"hosp_a_{uuid.uuid4().hex[:6]}@example.com",
            phone="555-0101",
            is_active=True,
        )
        hosp_b = Hospital(
            id=uuid.uuid4(),
            name=f"Apex Health Clinic {uuid.uuid4().hex[:6]}",
            address="200 Apex St",
            city="Metropolis",
            state="NY",
            email=f"hosp_b_{uuid.uuid4().hex[:6]}@example.com",
            phone="555-0202",
            is_active=True,
        )
        session.add_all([hosp_a, hosp_b])
        await session.flush()

        # 2. Doctor A (Hospital A) & Doctor B (Hospital B)
        doc_a_user = User(
            id=uuid.uuid4(),
            email=f"dr_a_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="pw",
            full_name="Dr. Alexander Wright",
            role="doctor",
            hospital_id=hosp_a.id,
            is_active=True,
        )
        doc_b_user = User(
            id=uuid.uuid4(),
            email=f"dr_b_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="pw",
            full_name="Dr. Beatrice Vance",
            role="doctor",
            hospital_id=hosp_b.id,
            is_active=True,
        )
        session.add_all([doc_a_user, doc_b_user])
        await session.flush()

        doc_a = Doctor(
            id=uuid.uuid4(),
            user_id=doc_a_user.id,
            hospital_id=hosp_a.id,
            specialty="Internal Medicine",
            qualification="MD",
            experience_years=12,
            is_available=True,
        )
        doc_b = Doctor(
            id=uuid.uuid4(),
            user_id=doc_b_user.id,
            hospital_id=hosp_b.id,
            specialty="Cardiology",
            qualification="MD",
            experience_years=9,
            is_available=True,
        )
        session.add_all([doc_a, doc_b])
        await session.flush()

        # 3. Patient 1 & Patient 2
        pat_1 = User(
            id=uuid.uuid4(),
            email=f"pat_1_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="pw",
            full_name="Charles Xavier",
            role="patient",
            is_active=True,
        )
        pat_2 = User(
            id=uuid.uuid4(),
            email=f"pat_2_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="pw",
            full_name="Diana Prince",
            role="patient",
            is_active=True,
        )
        session.add_all([pat_1, pat_2])
        await session.flush()

        # 4. Appointment: Patient 1 has an appointment with Doctor A
        appt_1 = Appointment(
            id=uuid.uuid4(),
            appointment_token=f"APPT-P12-{uuid.uuid4().hex[:6].upper()}",
            patient_id=pat_1.id,
            doctor_id=doc_a.id,
            hospital_id=hosp_a.id,
            appointment_date=date(2026, 11, 20),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status="scheduled",
            notes="Follow-up lab review.",
        )
        session.add(appt_1)
        await session.commit()

        ctx = {
            "hosp_a": hosp_a,
            "hosp_b": hosp_b,
            "doc_a_user": doc_a_user,
            "doc_a": doc_a,
            "doc_b_user": doc_b_user,
            "doc_b": doc_b,
            "pat_1": pat_1,
            "pat_2": pat_2,
            "appt_1": appt_1,
            "token_doc_a": create_access_token(user_id=doc_a_user.id, role="doctor"),
            "token_doc_b": create_access_token(user_id=doc_b_user.id, role="doctor"),
            "token_pat_1": create_access_token(user_id=pat_1.id, role="patient"),
            "token_pat_2": create_access_token(user_id=pat_2.id, role="patient"),
        }
        yield ctx

        # Teardown
        async with AsyncSessionLocal() as td_sess:
            await td_sess.execute(MedicalParameterCorrection.__table__.delete())
            await td_sess.execute(ExtractedMedicalParameter.__table__.delete())
            await td_sess.execute(MedicalReportAnalysis.__table__.delete())
            await td_sess.execute(MedicalReportReview.__table__.delete())
            await td_sess.execute(MedicalDocument.__table__.delete())
            await td_sess.execute(ClinicalAuditLog.__table__.delete().where(ClinicalAuditLog.patient_id.in_([pat_1.id, pat_2.id])))
            await td_sess.execute(Appointment.__table__.delete().where(Appointment.id == appt_1.id))
            await td_sess.execute(Doctor.__table__.delete().where(Doctor.id.in_([doc_a.id, doc_b.id])))
            await td_sess.execute(User.__table__.delete().where(User.id.in_([doc_a_user.id, doc_b_user.id, pat_1.id, pat_2.id])))
            await td_sess.execute(Hospital.__table__.delete().where(Hospital.id.in_([hosp_a.id, hosp_b.id])))
            await td_sess.commit()


# ===========================================================================
# 1. DOCUMENT PROCESSING & VALIDATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_upload_valid_digital_pdf(client: AsyncClient, p12_context):
    """Verifies successful upload, storage, and immediate synchronous analysis of valid PDF."""
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    pdf_bytes = create_sample_digital_pdf([
        "METROPOLIS CLINICAL LABORATORIES",
        "Patient: Charles Xavier | Date: 2026-11-01",
        "Complete Blood Count (CBC)",
        "Hemoglobin 14.5 g/dL (13.0 - 17.0)",
        "Platelet Count 250000 /uL (150000 - 450000)",
        "WBC Count 7200 /uL (4000 - 11000)",
    ])

    files = {"file": ("cbc_report.pdf", pdf_bytes, "application/pdf")}
    data = {"document_category": "Complete Blood Count (CBC)"}

    res = await client.post("/api/v1/medical-reports/upload", files=files, data=data, headers=headers)
    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["id"] is not None
    assert doc_data["original_filename"] == "cbc_report.pdf"
    assert doc_data["processing_status"] == "COMPLETED"
    assert doc_data["document_category"] == "Complete Blood Count (CBC)"

    # Verify analysis was created
    analysis_res = await client.get(f"/api/v1/medical-reports/{doc_data['id']}/analysis", headers=headers)
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()
    assert len(analysis["parameters"]) >= 3
    hgb = next((p for p in analysis["parameters"] if p["canonical_name"] == "Hemoglobin"), None)
    assert hgb is not None
    assert hgb["numeric_value"] == 14.5
    assert hgb["range_status"] == "WITHIN_RANGE"


@pytest.mark.asyncio
async def test_upload_invalid_file_rejected(client: AsyncClient, p12_context):
    """Verifies that non-PDF files and corrupt headers are rejected with 400 Bad Request."""
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    # Plain text file disguised as PDF
    fake_pdf = b"This is a text file without PDF magic bytes."
    files = {"file": ("fake.pdf", fake_pdf, "application/pdf")}

    res = await client.post("/api/v1/medical-reports/upload", files=files, headers=headers)
    assert res.status_code == 400
    assert "not a valid PDF" in res.json()["detail"]


@pytest.mark.asyncio
async def test_scanned_pdf_ocr_fallback(client: AsyncClient, p12_context):
    """
    Verifies that a scanned image-only PDF triggers the OCR fallback and extracts parameters.
    """
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    # Scanned image with no selectable text
    scanned_bytes = create_sample_scanned_pdf([
        "BIO-DIAGNOSTIC PATHOLOGY LAB",
        "HbA1c 7.4 % Ref: < 5.7",
        "Fasting Blood Glucose 135 mg/dL 70 - 100",
    ])

    files = {"file": ("scanned_diabetic_report.pdf", scanned_bytes, "application/pdf")}
    data = {"document_category": "Blood Glucose"}

    res = await client.post("/api/v1/medical-reports/upload", files=files, data=data, headers=headers)
    assert res.status_code == 201
    doc_data = res.json()

    analysis_res = await client.get(f"/api/v1/medical-reports/{doc_data['id']}/analysis", headers=headers)
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()
    assert analysis["ocr_applied_pages"] >= 1

    # Check extracted parameters via OCR
    param_names = [p["canonical_name"] for p in analysis["parameters"]]
    assert "HbA1c" in param_names or "Fasting Blood Glucose" in param_names


@pytest.mark.asyncio
async def test_duplicate_document_detection(client: AsyncClient, p12_context):
    """Verifies that duplicate document uploads for the same patient are cleanly detected."""
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    pdf_bytes = create_sample_digital_pdf([
        "Lipid Profile Test",
        "Total Cholesterol 240 mg/dL (< 200)",
        "Triglycerides 180 mg/dL (< 150)",
    ])

    files_1 = {"file": ("lipid_1.pdf", pdf_bytes, "application/pdf")}
    res_1 = await client.post("/api/v1/medical-reports/upload", files=files_1, headers=headers)
    assert res_1.status_code == 201
    doc_1_id = res_1.json()["id"]

    # Upload exact duplicate
    files_2 = {"file": ("lipid_1.pdf", pdf_bytes, "application/pdf")}
    res_2 = await client.post("/api/v1/medical-reports/upload", files=files_2, headers=headers)
    assert res_2.status_code == 201
    doc_2_id = res_2.json()["id"]

    # Reuses same document record
    assert doc_1_id == doc_2_id


# ===========================================================================
# 2. PARAMETER EXTRACTION & RANGE ANALYSIS TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_abnormal_and_critical_range_evaluation(client: AsyncClient, p12_context):
    """
    Verifies range status assignment:
    - BELOW_RANGE
    - ABOVE_RANGE
    - CRITICAL_REVIEW_REQUIRED
    """
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    # Severe acute anemia (Hb 6.2 < 7.0 critical) & elevated Creatinine (2.4 > 1.3 high)
    pdf_bytes = create_sample_digital_pdf([
        "METABOLIC & HEMATOLOGY REPORT",
        "Hemoglobin 6.2 g/dL 12.0 - 16.0",
        "Serum Creatinine 2.4 mg/dL 0.6 - 1.2",
        "Platelet Count 95000 /uL 150000 - 450000",
        "Total Cholesterol 175 mg/dL < 200",
    ])

    files = {"file": ("critical_report.pdf", pdf_bytes, "application/pdf")}
    res = await client.post("/api/v1/medical-reports/upload", files=files, headers=headers)
    assert res.status_code == 201
    doc_id = res.json()["id"]

    summary_res = await client.get(f"/api/v1/medical-reports/{doc_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()

    assert summary["critical_alerts_count"] >= 1
    assert "Hemoglobin" in summary["critical_parameters"]
    assert any("CRITICAL" in obs for obs in summary["important_observations"])

    analysis_res = await client.get(f"/api/v1/medical-reports/{doc_id}/analysis", headers=headers)
    params = analysis_res.json()["parameters"]

    hgb = next(p for p in params if p["canonical_name"] == "Hemoglobin")
    assert hgb["range_status"] == "CRITICAL_REVIEW_REQUIRED"
    assert hgb["is_critical"] is True

    creat = next(p for p in params if p["canonical_name"] == "Serum Creatinine")
    assert creat["range_status"] == "ABOVE_RANGE"

    plt = next(p for p in params if p["canonical_name"] == "Platelet Count")
    assert plt["range_status"] == "BELOW_RANGE"

    chol = next(p for p in params if p["canonical_name"] == "Total Cholesterol")
    assert chol["range_status"] == "WITHIN_RANGE"


# ===========================================================================
# 3. HISTORICAL REPORT COMPARISON TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_historical_report_comparison_and_trends(client: AsyncClient, p12_context):
    """
    Verifies comparison of 2 reports:
    - Calculates mathematical delta and % change
    - Assigns trend directions (INCREASING, DECREASING, STABLE)
    - Verifies unit compatibility check
    """
    ctx = p12_context
    headers = {"Authorization": f"Bearer {ctx['token_pat_1']}"}

    # Report 1: Initial visit
    pdf_1 = create_sample_digital_pdf([
        "COMPREHENSIVE METABOLIC PANEL",
        "Date: 2026-09-01",
        "HbA1c 8.2 % (< 5.7)",
        "Fasting Blood Glucose 160 mg/dL (70 - 100)",
        "Total Cholesterol 240 mg/dL (< 200)",
    ])
    res_1 = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("report_sep.pdf", pdf_1, "application/pdf")},
        data={"report_date": "2026-09-01"},
        headers=headers,
    )
    doc_1_id = res_1.json()["id"]

    # Report 2: 3-month follow-up after medication
    pdf_2 = create_sample_digital_pdf([
        "COMPREHENSIVE METABOLIC PANEL",
        "Date: 2026-11-20",
        "HbA1c 6.8 % (< 5.7)",
        "Fasting Blood Glucose 110 mg/dL (70 - 100)",
        "Total Cholesterol 195 mg/dL (< 200)",
    ])
    res_2 = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("report_nov.pdf", pdf_2, "application/pdf")},
        data={"report_date": "2026-11-20"},
        headers=headers,
    )
    doc_2_id = res_2.json()["id"]

    # Compare reports
    cmp_res = await client.get(
        f"/api/v1/medical-reports/compare/reports?document_ids={doc_1_id}&document_ids={doc_2_id}",
        headers=headers,
    )
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.json()

    assert cmp_data["total_compared_parameters"] >= 3
    a1c_comp = next((p for p in cmp_data["parameters"] if p["canonical_name"] == "HbA1c"), None)
    assert a1c_comp is not None
    assert a1c_comp["previous_value"] == 8.2
    assert a1c_comp["current_value"] == 6.8
    assert a1c_comp["delta"] == -1.4
    assert a1c_comp["trend"] == "DECREASING"
    assert a1c_comp["unit_compatible"] is True

    # Test Recharts trend endpoint for HbA1c
    trend_res = await client.get("/api/v1/medical-reports/trends/parameter?parameter_name=HbA1c", headers=headers)
    assert trend_res.status_code == 200
    trend = trend_res.json()
    assert trend["parameter_name"] == "HbA1c"
    assert len(trend["data_points"]) >= 2
    assert trend["data_points"][0]["value"] == 8.2
    assert trend["data_points"][1]["value"] == 6.8


# ===========================================================================
# 4. SECURITY, RBAC & IDOR PREVENTION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_security_rbac_and_cross_patient_idor(client: AsyncClient, p12_context):
    """
    Security verification:
    1. Patient 2 cannot access Patient 1's report (403 Forbidden).
    2. External Doctor B cannot access Patient 1's report without care relationship (403 Forbidden).
    3. Unauthorized download rejected (403 Forbidden).
    4. Patient cannot call doctor review or parameter correction (403 Forbidden).
    """
    ctx = p12_context
    headers_pat_1 = {"Authorization": f"Bearer {ctx['token_pat_1']}"}
    headers_pat_2 = {"Authorization": f"Bearer {ctx['token_pat_2']}"}
    headers_doc_a = {"Authorization": f"Bearer {ctx['token_doc_a']}"}
    headers_doc_b = {"Authorization": f"Bearer {ctx['token_doc_b']}"}

    # Patient 1 uploads a private report
    pdf = create_sample_digital_pdf(["Thyroid Profile", "TSH 3.2 uIU/mL (0.4 - 4.5)"])
    up_res = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("tsh.pdf", pdf, "application/pdf")},
        headers=headers_pat_1,
    )
    doc_id = up_res.json()["id"]

    # 1. Patient 2 attempts IDOR access to Patient 1's report
    p2_res = await client.get(f"/api/v1/medical-reports/{doc_id}", headers=headers_pat_2)
    assert p2_res.status_code == 403

    # 2. External Doctor B attempts unauthorized access
    doc_b_res = await client.get(f"/api/v1/medical-reports/{doc_id}", headers=headers_doc_b)
    assert doc_b_res.status_code == 403
    assert "Patient is not under your clinical care" in doc_b_res.json()["detail"]

    # 3. Patient 2 attempts unauthorized download
    p2_dl = await client.get(f"/api/v1/medical-reports/{doc_id}/download", headers=headers_pat_2)
    assert p2_dl.status_code == 403

    # 4. Patient attempts doctor-only review endpoint
    p1_rev = await client.post(
        f"/api/v1/medical-reports/{doc_id}/review",
        json={"review_status": "REVIEWED"},
        headers=headers_pat_1,
    )
    assert p1_rev.status_code == 403


# ===========================================================================
# 5. DOCTOR REVIEW & AUDITED PARAMETER CORRECTION
# ===========================================================================

@pytest.mark.asyncio
async def test_doctor_review_and_audited_parameter_correction(client: AsyncClient, p12_context):
    """
    Verifies doctor review and parameter correction:
    1. Authorized Doctor A reviews Patient 1's report.
    2. Doctor A corrects an OCR misread value with clinical rationale.
    3. Verifies prior value and rationale are preserved in MedicalParameterCorrection and ClinicalAuditLog.
    """
    ctx = p12_context
    headers_pat_1 = {"Authorization": f"Bearer {ctx['token_pat_1']}"}
    headers_doc_a = {"Authorization": f"Bearer {ctx['token_doc_a']}"}

    # Upload report
    pdf = create_sample_digital_pdf([
        "Liver Function Test",
        "Total Bilirubin 1.1 mg/dL (0.2 - 1.2)",
        "ALT 45 U/L (7 - 56)",
    ])
    up_res = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("lft.pdf", pdf, "application/pdf")},
        headers=headers_pat_1,
    )
    doc_id = up_res.json()["id"]

    # 1. Doctor A reviews report
    rev_payload = {
        "review_status": "REVIEWED",
        "clinical_notes": "Liver enzymes are within normal limits; continue current dietary management.",
    }
    rev_res = await client.post(
        f"/api/v1/medical-reports/{doc_id}/review",
        json=rev_payload,
        headers=headers_doc_a,
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["review_status"] == "REVIEWED"
    assert "Liver enzymes are within normal limits" in rev_data["clinical_notes"]

    # 2. Doctor A corrects a parameter (e.g. Bilirubin was misread as 1.1 instead of 1.4)
    analysis_res = await client.get(f"/api/v1/medical-reports/{doc_id}/analysis", headers=headers_doc_a)
    params = analysis_res.json()["parameters"]
    bili = next(p for p in params if p["canonical_name"] == "Total Bilirubin")

    corr_payload = {
        "corrected_value": "1.4",
        "correction_reason": "Correction based on official signed pathologist report: Bilirubin is 1.4 mg/dL.",
    }
    corr_res = await client.patch(
        f"/api/v1/medical-reports/{doc_id}/parameters/{bili['id']}",
        json=corr_payload,
        headers=headers_doc_a,
    )
    assert corr_res.status_code == 200
    corr_data = corr_res.json()
    assert corr_data["prior_value"] == "1.1"
    assert corr_data["corrected_value"] == "1.4"
    assert corr_data["correction_reason"] == corr_payload["correction_reason"]

    # 3. Verify in database: parameter updated and correction logged
    async with AsyncSessionLocal() as session:
        param_check = await session.execute(
            select(ExtractedMedicalParameter).where(ExtractedMedicalParameter.id == uuid.UUID(bili["id"]))
        )
        saved_param = param_check.scalar_one_or_none()
        assert saved_param.extracted_value == "1.4"
        assert saved_param.range_status == "ABOVE_RANGE"  # 1.4 is above high 1.2
        assert saved_param.verification_status == "DOCTOR_CORRECTED"

        # Check audit log
        audit_check = await session.execute(
            select(ClinicalAuditLog).where(
                ClinicalAuditLog.target_type == "extracted_medical_parameter",
                ClinicalAuditLog.action == "PARAMETER_CORRECTION",
            )
        )
        audit_log = audit_check.scalar_one_or_none()
        assert audit_log is not None
        assert audit_log.metadata_json["prior_value"] == "1.1"
        assert audit_log.metadata_json["corrected_value"] == "1.4"


# ===========================================================================
# 6. COMPLETE END-TO-END WORKFLOW VALIDATION
# ===========================================================================

@pytest.mark.asyncio
async def test_end_to_end_medical_report_analysis_workflow(client: AsyncClient, p12_context):
    """
    Validates complete 10-step clinical lifecycle:
    1. Patient authenticates.
    2. Patient uploads Kidney Function Test report.
    3. Document processing engine extracts parameters.
    4. Plain-language report summary is generated.
    5. Patient reviews extracted parameters and observations.
    6. Attending doctor accesses patient's report via care relationship.
    7. Doctor reviews parameters and submits clinical determination.
    8. Patient uploads subsequent follow-up report.
    9. System executes historical report comparison.
    10. Audit trail permanently preserves all actions.
    """
    ctx = p12_context
    headers_pat = {"Authorization": f"Bearer {ctx['token_pat_1']}"}
    headers_doc = {"Authorization": f"Bearer {ctx['token_doc_a']}"}

    # Step 2: Patient uploads Kidney Function Test
    kft_1 = create_sample_digital_pdf([
        "RENAL FUNCTION TEST (KFT)",
        "Date: 2026-08-15",
        "Serum Creatinine 1.8 mg/dL (0.6 - 1.2)",
        "Blood Urea 55 mg/dL (15 - 45)",
        "Uric Acid 6.5 mg/dL (3.5 - 7.2)",
    ])
    up_res = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("kft_aug.pdf", kft_1, "application/pdf")},
        data={"document_category": "Kidney Function Test (KFT)", "report_date": "2026-08-15"},
        headers=headers_pat,
    )
    assert up_res.status_code == 201
    doc_1_id = up_res.json()["id"]

    # Step 3 & 4: Plain-language summary
    summary_res = await client.get(f"/api/v1/medical-reports/{doc_1_id}/summary", headers=headers_pat)
    assert summary_res.status_code == 200
    summary_1 = summary_res.json()
    assert summary_1["total_parameters_extracted"] == 3
    assert "Serum Creatinine" in summary_1["above_range_parameters"]
    assert "Blood Urea" in summary_1["above_range_parameters"]

    # Step 6 & 7: Doctor reviews patient's report
    doc_review_res = await client.post(
        f"/api/v1/medical-reports/{doc_1_id}/review",
        json={"review_status": "REVIEWED", "clinical_notes": "Mild azotemia noted. Encourage oral hydration and repeat KFT in 2 months."},
        headers=headers_doc,
    )
    assert doc_review_res.status_code == 200

    # Step 8: Patient uploads follow-up report
    kft_2 = create_sample_digital_pdf([
        "RENAL FUNCTION TEST (KFT) - FOLLOW UP",
        "Date: 2026-10-25",
        "Serum Creatinine 1.3 mg/dL (0.6 - 1.2)",
        "Blood Urea 40 mg/dL (15 - 45)",
        "Uric Acid 5.8 mg/dL (3.5 - 7.2)",
    ])
    up_res_2 = await client.post(
        "/api/v1/medical-reports/upload",
        files={"file": ("kft_oct.pdf", kft_2, "application/pdf")},
        data={"document_category": "Kidney Function Test (KFT)", "report_date": "2026-10-25"},
        headers=headers_pat,
    )
    assert up_res_2.status_code == 201
    doc_2_id = up_res_2.json()["id"]

    # Step 9: Historical Comparison
    cmp_res = await client.get(
        f"/api/v1/medical-reports/compare/reports?document_ids={doc_1_id}&document_ids={doc_2_id}",
        headers=headers_pat,
    )
    assert cmp_res.status_code == 200
    cmp = cmp_res.json()

    creat_cmp = next(p for p in cmp["parameters"] if p["canonical_name"] == "Serum Creatinine")
    assert creat_cmp["previous_value"] == 1.8
    assert creat_cmp["current_value"] == 1.3
    assert creat_cmp["delta"] == -0.5
    assert creat_cmp["trend"] == "DECREASING"

    urea_cmp = next(p for p in cmp["parameters"] if p["canonical_name"] == "Blood Urea")
    assert urea_cmp["previous_value"] == 55.0
    assert urea_cmp["current_value"] == 40.0
    assert urea_cmp["delta"] == -15.0
    assert urea_cmp["trend"] == "DECREASING"

    # Step 10: Verify Audit Trail
    async with AsyncSessionLocal() as session:
        audits = await session.execute(
            select(ClinicalAuditLog).where(
                ClinicalAuditLog.patient_id == ctx["pat_1"].id
            )
        )
        actions = [a.action for a in audits.scalars().all()]
        assert "MEDICAL_DOCUMENT_UPLOAD" in actions
        assert "MEDICAL_REPORT_REVIEW" in actions
