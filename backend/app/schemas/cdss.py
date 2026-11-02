"""
Pydantic Schemas for AI-Powered Clinical Decision Support System (CDSS).
Updated for Phase 11.2: Clinical Governance, Real-World Validation & Safety Monitoring.

Covers:
- Clinical note summarization, structured symptoms, negation, uncertainty, family history, and contradiction detection.
- Documentation completeness auditing.
- Longitudinal patient medical history insights with strict 4-state allergy safety handling.
- Medication safety (duplicate check, high-risk drug-drug interactions with full provenance, missing instructions).
- Accredited clinical practice guideline matching with 5-state freshness statuses.
- Knowledge base governance metadata with complete version history and approval tracking.
- Structured CDSS safety monitoring events (acknowledgement, dismissal).
- Clinician feedback mechanism.
- Comprehensive CDSS evaluation payload.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Clinical Note Summarization & Symptom Structuring
# ---------------------------------------------------------------------------
class NoteSummaryInput(BaseModel):
    """Input payload representing active or draft consultation notes."""
    chief_complaint: str = Field(..., min_length=2, description="Patient's primary presenting concern")
    symptoms: Optional[str] = Field(None, description="Reported symptoms and clinical history")
    clinical_observations: Optional[str] = Field(None, description="Clinician observations during encounter")
    examination_notes: Optional[str] = Field(None, description="Physical examination findings")
    diagnosis_summary: Optional[str] = Field(None, description="Diagnostic conclusion or working diagnosis")
    treatment_plan: Optional[str] = Field(None, description="Prescribed therapeutic and pharmacological plan")
    doctor_recommendations: Optional[str] = Field(None, description="Lifestyle, dietary, or rest guidance")
    follow_up_instructions: Optional[str] = Field(None, description="Return directives or safety-net advice")


class SymptomCategory(BaseModel):
    """Structured clinical breakdown of an extracted symptom with negation, uncertainty, and provenance."""
    symptom_name: str
    status: str = Field("PRESENT", description="PRESENT | NEGATED | UNCERTAIN")
    is_negated: bool = Field(False, description="True if patient denies or symptom is absent")
    is_uncertain: bool = Field(False, description="True if statement indicates clinical suspicion or uncertainty")
    is_family_history: bool = Field(False, description="True if symptom or diagnosis pertains to family member, not patient")
    certainty: str = Field("CONFIRMED", description="CONFIRMED | SUSPECTED | UNCERTAIN")
    characteristics: Optional[str] = None
    severity_assessment: Optional[str] = None  # Severe, Moderate, Mild, Absent, Not specified
    duration_onset: Optional[str] = None
    source_attribution: str = Field(
        "CURRENT_ENCOUNTER",
        description="CURRENT_ENCOUNTER | HISTORICAL_RECORD | FAMILY_HISTORY"
    )
    clinical_context: Optional[str] = None


class ClinicalNoteSummaryResponse(BaseModel):
    """AI-generated concise clinical encounter summary."""
    executive_summary: str
    chief_complaint: str
    structured_symptoms: List[SymptomCategory]
    pertinent_negatives: List[str] = Field(
        default_factory=list,
        description="Explicit list of denied/absent symptoms (e.g. denies chest pain, no nausea)"
    )
    uncertain_statements: List[str] = Field(
        default_factory=list,
        description="Statements documented with diagnostic uncertainty (e.g. possible chest infection)"
    )
    family_history_notes: List[str] = Field(
        default_factory=list,
        description="Extracted family medical history (e.g. mother had diabetes) strictly isolated from patient presentation"
    )
    conditional_directives: List[str] = Field(
        default_factory=list,
        description="Contingency directives (e.g. if fever persists > 3 days, return for review)"
    )
    contradictions_detected: List[str] = Field(
        default_factory=list,
        description="Clinical discordances detected across sections (e.g. fever in symptoms vs afebrile in vitals)"
    )
    clinical_observations_summary: str
    examination_findings_summary: str
    diagnostic_impression: str
    treatment_plan_summary: str
    follow_up_considerations: str
    provenance_sources: List[str] = Field(
        default_factory=lambda: ["CURRENT_ENCOUNTER", "AI_SYNTHESIS"],
        description="Explicit tagging of data sources"
    )
    disclaimer: str = Field(
        default="AI-generated assistive summary. Requires physician review and verification before clinical use."
    )


# ---------------------------------------------------------------------------
# 2. Documentation Completeness Review
# ---------------------------------------------------------------------------
class DocumentationCheckItem(BaseModel):
    section: str
    is_complete: bool
    status: str  # "complete" | "warning" | "missing"
    message: str
    recommendation: Optional[str] = None


class DocumentationCompletenessResponse(BaseModel):
    """Audit of clinical documentation thoroughness."""
    completeness_score: int = Field(..., ge=0, le=100, description="Percentage score 0-100")
    overall_status: str  # "optimal" | "acceptable" | "incomplete"
    total_sections_checked: int
    completed_sections: int
    items: List[DocumentationCheckItem]
    actionable_recommendations: List[str]


# ---------------------------------------------------------------------------
# 3. Patient History Insights & Allergy Safety
# ---------------------------------------------------------------------------
class HistoryDiagnosisItem(BaseModel):
    diagnosis_name: str
    diagnosis_code: Optional[str] = None
    status: str
    diagnosis_date: str


class HistoryPrescriptionItem(BaseModel):
    prescription_number: str
    medication_name: str
    dosage: str
    frequency: str
    prescription_date: str
    is_active: bool


class PatientHistoryInsightsResponse(BaseModel):
    """Longitudinal clinical insights synthesized from existing EHR records with strict allergy safety."""
    patient_id: str
    patient_name: str
    total_recorded_consultations: int
    active_diagnoses: List[HistoryDiagnosisItem]
    chronic_conditions: List[HistoryDiagnosisItem]
    resolved_diagnoses: List[HistoryDiagnosisItem]
    active_prescriptions: List[HistoryPrescriptionItem]
    documented_allergies: List[str]
    allergy_documentation_status: str = Field(
        "NOT_DOCUMENTED",
        description="CONFIRMED_NO_KNOWN_ALLERGIES | DOCUMENTED_ALLERGIES | NOT_DOCUMENTED | REQUIRES_VERIFICATION"
    )
    allergy_safety_warning: Optional[str] = Field(
        None,
        description="Prominent safety warning when allergy information is unconfirmed or not documented"
    )
    allergy_verification_date: Optional[str] = None
    adherence_follow_up_summary: str
    clinical_caution_flags: List[str]
    disclaimer: str = Field(
        default="Synthesized exclusively from authorized electronic health records on file. Unrecorded conditions may exist."
    )


# ---------------------------------------------------------------------------
# 4. Medication Safety Support
# ---------------------------------------------------------------------------
class MedicationItemInput(BaseModel):
    medication_name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = "Oral"
    instructions: Optional[str] = None


class DuplicateMedicationAlert(BaseModel):
    medication_name: str
    duplicate_type: str  # "EXACT_NAME" | "PHARMACOLOGICAL_CLASS"
    conflict_with: str
    severity: str  # "HIGH" | "MODERATE"
    message: str
    clinical_rationale: str
    evidence_source: str
    recommended_action: str


class DrugInteractionAlert(BaseModel):
    interaction_id: str
    primary_medication: str
    secondary_medication: str
    primary_class: str
    secondary_class: str
    severity: str  # "CRITICAL" | "HIGH" | "MODERATE" | "LOW"
    clinical_certainty: str = Field("ESTABLISHED", description="ESTABLISHED | PRECAUTIONARY")
    evidence_classification: str = Field("CLASS_I_STRONG", description="CLASS_I_STRONG | CLASS_II_MODERATE | CONSENSUS_EXPERT | POSTMARKETING_SURVEILLANCE")
    rule_version: str = Field("1.2")
    clinical_mechanism: str
    risk_summary: str
    patient_risk_factors: List[str] = Field(default_factory=list)
    recommended_action: str
    evidence_source: str
    source_url: str
    publication_date: str
    last_reviewed_date: str
    next_review_date: str = Field("2027-10-15")
    approved_by: str = Field("Dr. Marcus Vance, MD, FACP")
    approval_status: str = Field("APPROVED", description="APPROVED | PENDING_REVIEW | FLAGGED_FOR_REVISION")
    knowledge_base_version: str


class MissingInstructionAlert(BaseModel):
    medication_name: str
    severity: str = Field("HIGH", description="HIGH | MODERATE")
    missing_fields: List[str]
    message: str
    clinical_impact: str


class ContraindicationAlert(BaseModel):
    """Screening alert for medication use in clinically contraindicated conditions."""
    rule_id: str
    medication_name: str
    contraindicated_condition: str
    severity: str = Field("CRITICAL", description="CRITICAL | HIGH")
    clinical_mechanism: str
    clinical_risk: str
    recommended_action: str
    evidence_source: str
    source_url: Optional[str] = None
    rule_version: str = "1.3"
    evidence_classification: str = "CLASS_I_STRONG"
    validation_status: str = "CLINICALLY_VALIDATED"
    kb_version: str = "2026.11.3-v1.3"


class MedicationSafetyCheckRequest(BaseModel):
    items: List[MedicationItemInput]
    patient_id: Optional[str] = None  # If provided, cross-checks against active historical prescriptions and allergies


class MedicationSafetyCheckResponse(BaseModel):
    """Safety evaluation of prescribed medications."""
    total_medications_evaluated: int
    overall_safety_status: str  # "SAFE" | "REVIEW_RECOMMENDED" | "WARNING_FLAGGED"
    duplicate_alerts: List[DuplicateMedicationAlert]
    interaction_alerts: List[DrugInteractionAlert]
    contraindication_alerts: List[ContraindicationAlert] = Field(default_factory=list)
    instruction_alerts: List[MissingInstructionAlert]
    allergy_alerts: List[str]
    allergy_safety_status: str = Field(
        "NOT_DOCUMENTED",
        description="CONFIRMED_NO_KNOWN_ALLERGIES | DOCUMENTED_ALLERGIES | NOT_DOCUMENTED | REQUIRES_VERIFICATION"
    )
    allergy_warning_banner: Optional[str] = None
    verification_coverage_note: str = Field(
        default="Interaction checks are verified against established peer-reviewed clinical pharmacology reference tables. Uncatalogued substances require independent pharmacist review."
    )
    disclaimer: str = Field(
        default="Assistive drug-safety check. Does not replace clinical pharmacological evaluation by a licensed practitioner."
    )


# ---------------------------------------------------------------------------
# 5. Clinical Practice Guidelines Assistant
# ---------------------------------------------------------------------------
class GuidelineRecommendation(BaseModel):
    category: str  # "First-line Pharmacotherapy" | "Lifestyle & Non-Pharmacological" | "Monitoring" | "Red Flags / Referral"
    text: str


class ClinicalGuidelineItem(BaseModel):
    guideline_id: str
    condition_name: str
    icd10_codes: List[str]
    publishing_authority: str
    guideline_title: str
    publication_year: int
    publication_date: str
    last_updated_date: str
    last_verified_date: str
    next_review_date: str = Field("2027-10-15")
    version: str
    freshness_status: str = Field(
        "CURRENT_VERIFIED",
        description="CURRENT_VERIFIED | REVIEW_REQUIRED | SUPERSEDED | UNDER_REVIEW | UNVERIFIED"
    )
    validation_status: str = Field(
        "CLINICALLY_VALIDATED",
        description="CLINICALLY_VALIDATED | PROVISIONAL_EVIDENCE | OUTDATED_WARNING | UNVERIFIED_EVIDENCE"
    )
    is_review_overdue: bool = False
    days_until_review: int = 0
    evidence_classification: str = Field("CLASS_I_STRONG", description="CLASS_I_STRONG | CLASS_II_MODERATE | CONSENSUS_EXPERT")
    approved_by: str = Field("National Specialty College Consensus Committee")
    approval_status: str = Field("APPROVED", description="APPROVED | PENDING_REVIEW | FLAGGED_FOR_REVISION")
    source_url: str
    summary: str
    applicable_clinical_context: str
    recommendations: List[GuidelineRecommendation]
    evidence_level: str  # "Grade A (High)", "Grade B (Moderate)", "Expert Consensus"
    uncertainty_statement: str


class ClinicalGuidelineResponse(BaseModel):
    matched_guidelines: List[ClinicalGuidelineItem]
    total_matched: int
    query_diagnosis: Optional[str] = None
    query_specialty: Optional[str] = None
    disclaimer: str = Field(
        default="Clinical guidelines provide evidence-based population principles and should be tailored to individual patient presentation, comorbidities, and clinical judgment."
    )


# ---------------------------------------------------------------------------
# 6. Knowledge Base Governance Metadata
# ---------------------------------------------------------------------------
class KBVersionHistoryEntry(BaseModel):
    version: str
    release_date: str
    reviewed_by: str
    changes_summary: str
    total_rules: int


class KnowledgeBaseMetadata(BaseModel):
    version: str
    last_reviewed: str
    next_scheduled_review: str = Field("2027-04-15")
    clinical_reviewer: str
    governance_board: str = Field("MediSmart AI Clinical Oversight Committee")
    total_active_interaction_rules: int
    total_active_guidelines: int
    total_pharmacological_classes: int
    governance_policy: str
    version_history: List[KBVersionHistoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 7. Safety Monitoring & Clinician Feedback
# ---------------------------------------------------------------------------
class CDSSSafetyEventAcknowledgeRequest(BaseModel):
    """Clinician action to acknowledge or dismiss a high-risk CDSS warning."""
    event_id: Optional[str] = None
    rule_identifier: str
    appointment_id: Optional[str] = None
    action: str = Field("ACKNOWLEDGE", description="ACKNOWLEDGE | DISMISS")
    dismissal_reason: Optional[str] = Field(None, description="Clinical rationale if warning is dismissed")


class CDSSSafetyEventResponse(BaseModel):
    id: str
    rule_identifier: Optional[str] = None
    warning_category: str
    warning_severity: str
    action_taken: str
    is_acknowledged: bool = True
    dismissal_reason: Optional[str] = None
    kb_version: str
    recorded_at: str


class CDSSFeedbackInput(BaseModel):
    """Physician feedback on CDSS evaluation accuracy and clinical utility."""
    feedback_type: str = Field(
        ...,
        description="RELEVANT_ALERT | IRRELEVANT_ALERT | INCORRECT_ALERT | MISSING_INTERACTION | OUTDATED_GUIDELINE | INCORRECT_SYMPTOM_EXTRACTION | GENERAL_FEEDBACK"
    )
    target_type: str = Field(
        ...,
        description="interaction_rule | guideline | symptom_extraction | general"
    )
    target_id: Optional[str] = Field(None, description="Identifier of the rule or guideline (e.g. DD-WAR-ASA)")
    clinician_comment: str = Field(..., min_length=3, description="Physician's clinical feedback rationale")
    appointment_id: Optional[str] = None


class CDSSFeedbackResponse(BaseModel):
    id: str
    doctor_id: str
    feedback_type: str
    target_type: str
    target_id: Optional[str] = None
    clinician_comment: str
    review_status: str
    kb_version: str
    created_at: str
    message: str = Field(
        default="Feedback recorded successfully. A clinical pharmacologist will review this submission during the next governance cycle."
    )


# ---------------------------------------------------------------------------
# 8. Explainable AI (XAI) & Clinical Intelligence Validation
# ---------------------------------------------------------------------------
class EvidenceBreakdown(BaseModel):
    """Structured breakdown separating documented facts, clinical hypotheses, and algorithmic outputs."""
    clinical_facts: List[str] = Field(
        default_factory=list,
        description="Verified patient facts documented in EHR or current consultation (e.g. diagnoses, age, lab flags, active Rx)",
    )
    suspected_conditions: List[str] = Field(
        default_factory=list,
        description="Provisional impressions or clinical uncertainty extracted from consultation notes",
    )
    algorithmic_predictions: List[str] = Field(
        default_factory=list,
        description="Machine learning scores, heuristic thresholds, or automated rule activations",
    )


class ExplainableRecommendation(BaseModel):
    """Transparent clinical recommendation with complete reasoning, rule provenance, and uncertainty metrics."""
    recommendation_id: str
    category: str = Field(..., description="MEDICATION_SAFETY | CLINICAL_GUIDELINE | DOCUMENTATION_AUDIT | CONTRAINDICATION")
    domain: Optional[str] = None
    recommendation_summary: str
    clinical_reasoning: str
    evidence: EvidenceBreakdown
    evidence_breakdown: Optional[EvidenceBreakdown] = None
    patient_risk_factors: List[str] = Field(default_factory=list)
    supporting_rules: List[str] = Field(default_factory=list)
    evidence_classification: str = Field("CLASS_I_STRONG", description="CLASS_I_STRONG | CLASS_IIA_MODERATE | CLASS_IIB_WEAK | CLASS_III_HARM")
    validation_status: str = Field("CLINICALLY_VALIDATED", description="CLINICALLY_VALIDATED | PROVISIONAL_EVIDENCE | OUTDATED_WARNING | UNVERIFIED_EVIDENCE")
    kb_version: str = "2026.11.3-v1.3"
    confidence_score: float = Field(0.95, ge=0.0, le=1.0)
    certainty_level: str = Field("HIGH_CONFIDENCE_FACT", description="HIGH_CONFIDENCE_FACT | MODERATE_CLINICAL_HYPOTHESIS | ALGORITHMIC_ALERT")
    is_review_overdue: bool = False
    source_citation: str
    source_url: Optional[str] = None


# ---------------------------------------------------------------------------
# 9. Clinical Safety Dashboard & Governance Analytics
# ---------------------------------------------------------------------------
class FeedbackStats(BaseModel):
    total_feedback: int = 0
    total_submissions: int = 0
    by_type: dict = Field(default_factory=dict)
    submissions_by_type: dict = Field(default_factory=dict)
    pending_review_count: int = 0
    pending_review: int = 0
    resolved_count: int = 0


class KBGovernanceStatus(BaseModel):
    version: str
    total_active_rules: int
    overdue_guidelines_count: int
    governance_board: str
    last_reviewed: str
    next_scheduled_review: str
    guidelines_status_breakdown: dict = Field(default_factory=dict)
    interaction_rules_count: int
    contraindication_rules_count: int


class SafetyEventTrend(BaseModel):
    date: str
    total: int
    acknowledged: int
    dismissed: int
    unresolved: int


class CDSSSafetyDashboardResponse(BaseModel):
    """Consolidated safety monitoring and governance dashboard for authorized hospital administrators."""
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    moderate_alerts: int
    informational_alerts: int
    acknowledged_alerts: int
    dismissed_alerts: int
    unresolved_alerts: int
    resolution_rate: float
    # Aliases and enriched analytics
    acknowledged_count: Optional[int] = None
    dismissed_count: Optional[int] = None
    unresolved_count: Optional[int] = None
    resolution_rate_percent: Optional[float] = None
    feedback_statistics: FeedbackStats
    clinician_feedback_stats: Optional[FeedbackStats] = None
    knowledge_base_status: KBGovernanceStatus
    overdue_guidelines_count: int = 0
    overdue_guidelines: List[ClinicalGuidelineItem] = Field(default_factory=list)
    category_breakdown: dict = Field(default_factory=dict)
    categories_breakdown: Optional[dict] = None
    recent_safety_events: List[CDSSSafetyEventResponse] = Field(default_factory=list)
    safety_event_trends: List[SafetyEventTrend] = Field(default_factory=list)
    daily_trends: Optional[List[SafetyEventTrend]] = None


# ---------------------------------------------------------------------------
# 10. Comprehensive CDSS Evaluation (Doctor Workspace)
# ---------------------------------------------------------------------------
class CDSSComprehensiveRequest(BaseModel):
    """Full encounter evaluation payload submitted from the doctor workspace."""
    appointment_id: Optional[str] = None
    patient_id: Optional[str] = None
    notes: NoteSummaryInput
    prescriptions: List[MedicationItemInput] = Field(default_factory=list)
    diagnosis_name: Optional[str] = None
    diagnosis_code: Optional[str] = None


class CDSSComprehensiveResponse(BaseModel):
    """Unified response consolidating all CDSS insights."""
    summary: ClinicalNoteSummaryResponse
    documentation_completeness: DocumentationCompletenessResponse
    medication_safety: MedicationSafetyCheckResponse
    guidelines: ClinicalGuidelineResponse
    explainable_recommendations: List[ExplainableRecommendation] = Field(default_factory=list)
    patient_insights: Optional[PatientHistoryInsightsResponse] = None
    kb_metadata: Optional[KnowledgeBaseMetadata] = None
    ai_safety_notice: str = Field(
        default="CLINICAL ASSISTIVE NOTICE: This system provides clinical decision support only. It does not independently diagnose, prescribe, or modify medical records. Final clinical responsibility remains entirely with the attending physician."
    )
