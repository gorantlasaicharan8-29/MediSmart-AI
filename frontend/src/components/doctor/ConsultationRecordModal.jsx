import React, { useState, useEffect } from 'react'
import {
  createConsultationNote,
  getConsultationByAppointment,
  amendPrescription,
  evaluateCDSS,
  acknowledgeCDSSSafetyEvent,
  submitCDSSFeedback,
} from '../../services/api'
import { Badge, Button, ClinicalIcon, Modal, ModalHeader, ModalBody, ModalFooter, Skeleton } from '../ui'

export default function ConsultationRecordModal({
  appointment = null,
  isOpen = false,
  onClose = () => {},
  onSaved = () => {},
}) {
  const [existingNote, setExistingNote] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)
  const [activeTab, setActiveTab] = useState('notes') // 'notes' | 'prescriptions' | 'followup'

  // Form State
  const [chiefComplaint, setChiefComplaint] = useState('')
  const [symptoms, setSymptoms] = useState('')
  const [clinicalObservations, setClinicalObservations] = useState('')
  const [examinationNotes, setExaminationNotes] = useState('')
  const [diagnosisSummary, setDiagnosisSummary] = useState('')
  const [treatmentPlan, setTreatmentPlan] = useState('')
  const [doctorRecommendations, setDoctorRecommendations] = useState('')

  // Structured Diagnoses
  const [diagnosisName, setDiagnosisName] = useState('')
  const [diagnosisCode, setDiagnosisCode] = useState('')
  const [diagnosisDesc, setDiagnosisDesc] = useState('')

  // Prescription Items
  const [prescriptionNotes, setPrescriptionNotes] = useState('')
  const [amendmentReason, setAmendmentReason] = useState('')
  const [rxItems, setRxItems] = useState([
    { medication_name: '', dosage: '', frequency: '', duration: '', route: 'Oral', instructions: '' }
  ])

  // Follow-up
  const [todayStr] = useState(() => new Date().toISOString().split('T')[0])
  const [followUpDate, setFollowUpDate] = useState('')
  const [followUpInstructions, setFollowUpInstructions] = useState('')

  // CDSS State
  const [cdssData, setCdssData] = useState(null)
  const [isCdssLoading, setIsCdssLoading] = useState(false)
  const [cdssError, setCdssError] = useState(null)
  const [cdssSubTab, setCdssSubTab] = useState('all') // 'all' | 'summary' | 'completeness' | 'safety' | 'guidelines' | 'history'

  // Phase 11.2: CDSS Governance, Safety Events & Feedback State
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState({})
  const [dismissModalRule, setDismissModalRule] = useState(null)
  const [dismissReasonInput, setDismissReasonInput] = useState('')
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [feedbackTarget, setFeedbackTarget] = useState({ targetType: 'cdss_encounter', targetId: '', ruleId: '' })
  const [feedbackType, setFeedbackType] = useState('RELEVANT_ALERT')
  const [feedbackComment, setFeedbackComment] = useState('')
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false)
  const [feedbackStatusMessage, setFeedbackStatusMessage] = useState(null)
  const [showVersionHistory, setShowVersionHistory] = useState(false)

  const handleAcknowledgeAlert = async (alert) => {
    const ruleKey = alert.rule_id || alert.rule_identifier
    try {
      await acknowledgeCDSSSafetyEvent({
        event_id: ruleKey,
        rule_identifier: ruleKey,
        action: 'ACKNOWLEDGE',
      })
      setAcknowledgedAlerts((prev) => ({
        ...prev,
        [ruleKey]: { action: 'ACKNOWLEDGE', reason: '' },
      }))
    } catch (err) {
      console.error('Failed to acknowledge CDSS alert', err)
      setAcknowledgedAlerts((prev) => ({
        ...prev,
        [ruleKey]: { action: 'ACKNOWLEDGE', reason: '' },
      }))
    }
  }

  const handleDismissAlert = async () => {
    if (!dismissModalRule || !dismissReasonInput.trim()) return
    const ruleKey = dismissModalRule.rule_id || dismissModalRule.rule_identifier
    try {
      await acknowledgeCDSSSafetyEvent({
        event_id: ruleKey,
        rule_identifier: ruleKey,
        action: 'DISMISS',
        dismissal_reason: dismissReasonInput.trim(),
      })
      setAcknowledgedAlerts((prev) => ({
        ...prev,
        [ruleKey]: { action: 'DISMISS', reason: dismissReasonInput.trim() },
      }))
      setDismissModalRule(null)
      setDismissReasonInput('')
    } catch (err) {
      console.error('Failed to dismiss CDSS alert', err)
      setAcknowledgedAlerts((prev) => ({
        ...prev,
        [ruleKey]: { action: 'DISMISS', reason: dismissReasonInput.trim() },
      }))
      setDismissModalRule(null)
      setDismissReasonInput('')
    }
  }

  const handleSubmitFeedback = async (e) => {
    e.preventDefault()
    if (!feedbackComment.trim()) return
    setIsSubmittingFeedback(true)
    setFeedbackStatusMessage(null)
    try {
      await submitCDSSFeedback({
        feedback_type: feedbackType,
        target_type: feedbackTarget.targetType || 'cdss_encounter',
        target_id: feedbackTarget.targetId || (appointment ? appointment.id : null),
        rule_id: feedbackTarget.ruleId || null,
        clinician_comment: feedbackComment.trim(),
        suggested_correction: null,
      })
      setFeedbackStatusMessage({ type: 'success', text: 'Feedback submitted for Clinical Governance Board review.' })
      setTimeout(() => {
        setShowFeedbackModal(false)
        setFeedbackStatusMessage(null)
        setFeedbackComment('')
      }, 1500)
    } catch (err) {
      setFeedbackStatusMessage({ type: 'error', text: err.message || 'Failed to submit feedback.' })
    } finally {
      setIsSubmittingFeedback(false)
    }
  }

  const runCDSSAnalysis = async () => {
    if (!appointment) return
    setIsCdssLoading(true)
    setCdssError(null)
    try {
      const payload = {
        appointment_id: appointment.id,
        patient_id: appointment.patient_id,
        notes: {
          chief_complaint: chiefComplaint || appointment.notes || 'Routine consultation encounter',
          symptoms: symptoms || null,
          clinical_observations: clinicalObservations || null,
          examination_notes: examinationNotes || null,
          diagnosis_summary: diagnosisSummary || null,
          treatment_plan: treatmentPlan || null,
          doctor_recommendations: doctorRecommendations || null,
          follow_up_instructions: followUpInstructions || null,
        },
        prescriptions: rxItems.filter((it) => it.medication_name && it.medication_name.trim()),
        diagnosis_name: diagnosisName || null,
        diagnosis_code: diagnosisCode || null,
      }
      const res = await evaluateCDSS(payload)
      setCdssData(res)
    } catch (err) {
      setCdssError(err.message || 'Failed to generate clinical decision support evaluation.')
    } finally {
      setIsCdssLoading(false)
    }
  }

  // Load existing note when modal opens
  useEffect(() => {
    let isMounted = true
    if (!isOpen || !appointment?.id) {
      setExistingNote(null)
      setError(null)
      setSuccessMsg(null)
      return
    }

    setIsLoading(true)
    setError(null)
    setSuccessMsg(null)

    getConsultationByAppointment(appointment.id)
      .then((res) => {
        if (isMounted) {
          setExistingNote(res)
          // Populate fields
          setChiefComplaint(res.chief_complaint || '')
          setSymptoms(res.symptoms || '')
          setClinicalObservations(res.clinical_observations || '')
          setExaminationNotes(res.examination_notes || '')
          setDiagnosisSummary(res.diagnosis_summary || '')
          setTreatmentPlan(res.treatment_plan || '')
          setDoctorRecommendations(res.doctor_recommendations || '')
          setFollowUpDate(res.follow_up_recommended_date || '')
          setFollowUpInstructions(res.follow_up_instructions || '')

          if (res.diagnoses?.length > 0) {
            setDiagnosisName(res.diagnoses[0].diagnosis_name || '')
            setDiagnosisCode(res.diagnoses[0].diagnosis_code || '')
            setDiagnosisDesc(res.diagnoses[0].clinical_description || '')
          }

          if (res.prescriptions?.length > 0 && res.prescriptions[0].items?.length > 0) {
            setPrescriptionNotes(res.prescriptions[0].notes || '')
            setRxItems(res.prescriptions[0].items.map((it) => ({
              medication_name: it.medication_name,
              dosage: it.dosage,
              frequency: it.frequency,
              duration: it.duration,
              route: it.route || 'Oral',
              instructions: it.instructions || '',
            })))
          }
        }
      })
      .catch(() => {
        if (isMounted) {
          setExistingNote(null)
          // Pre-populate chief complaint from appointment notes if available
          setChiefComplaint(appointment.notes || '')
          setSymptoms('')
          setClinicalObservations('')
          setExaminationNotes('')
          setDiagnosisSummary('')
          setTreatmentPlan('')
          setDoctorRecommendations('')
          setDiagnosisName('')
          setDiagnosisCode('')
          setDiagnosisDesc('')
          setRxItems([{ medication_name: '', dosage: '', frequency: '', duration: '', route: 'Oral', instructions: '' }])
          setFollowUpDate('')
          setFollowUpInstructions('')
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [isOpen, appointment?.id, appointment?.notes])

  // Prescription item row helpers
  const handleAddRxItem = () => {
    setRxItems([
      ...rxItems,
      { medication_name: '', dosage: '', frequency: '', duration: '', route: 'Oral', instructions: '' }
    ])
  }

  const handleRemoveRxItem = (idx) => {
    if (rxItems.length <= 1) return
    setRxItems(rxItems.filter((_, i) => i !== idx))
  }

  const handleRxItemChange = (idx, field, val) => {
    const updated = [...rxItems]
    updated[idx][field] = val
    setRxItems(updated)
  }

  // Handle Form Submission
  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!appointment?.id || isSaving) return

    if (!chiefComplaint.trim()) {
      setError('Chief Complaint is required.')
      return
    }
    if (!diagnosisSummary.trim()) {
      setError('Diagnosis Summary is required.')
      return
    }
    if (!treatmentPlan.trim()) {
      setError('Treatment Plan is required.')
      return
    }

    setIsSaving(true)
    setError(null)
    setSuccessMsg(null)

    // Build diagnoses array
    const diagnosesPayload = []
    if (diagnosisName.trim()) {
      diagnosesPayload.push({
        diagnosis_name: diagnosisName.trim(),
        clinical_description: diagnosisDesc.trim() || null,
        diagnosis_code: diagnosisCode.trim() || null,
        status: 'active',
      })
    }

    // Build prescription payload
    const validItems = rxItems.filter((it) => it.medication_name.trim() && it.dosage.trim())
    let prescriptionPayload = null
    if (validItems.length > 0) {
      prescriptionPayload = {
        notes: prescriptionNotes.trim() || null,
        items: validItems.map((it) => ({
          medication_name: it.medication_name.trim(),
          dosage: it.dosage.trim(),
          frequency: it.frequency.trim() || 'Once daily',
          duration: it.duration.trim() || '7 days',
          route: it.route.trim() || 'Oral',
          instructions: it.instructions.trim() || null,
        })),
      }
    }

    const payload = {
      appointment_id: appointment.id,
      chief_complaint: chiefComplaint.trim(),
      symptoms: symptoms.trim() || null,
      clinical_observations: clinicalObservations.trim() || null,
      examination_notes: examinationNotes.trim() || null,
      diagnosis_summary: diagnosisSummary.trim(),
      treatment_plan: treatmentPlan.trim(),
      doctor_recommendations: doctorRecommendations.trim() || null,
      follow_up_recommended_date: followUpDate || null,
      follow_up_instructions: followUpInstructions.trim() || null,
      diagnoses: diagnosesPayload,
      prescription: prescriptionPayload,
    }

    try {
      // If an active prescription already exists and amendment reason is supplied, amend it explicitly
      const activeRx = existingNote?.prescriptions?.find((rx) => rx.is_active)
      if (activeRx && validItems.length > 0 && amendmentReason.trim()) {
        await amendPrescription(activeRx.id, {
          amendment_reason: amendmentReason.trim(),
          notes: prescriptionNotes.trim() || null,
          items: validItems.map((it) => ({
            medication_name: it.medication_name.trim(),
            dosage: it.dosage.trim(),
            frequency: it.frequency.trim() || 'Once daily',
            duration: it.duration.trim() || '7 days',
            route: it.route.trim() || 'Oral',
            instructions: it.instructions.trim() || null,
          })),
        })
        payload.prescription = null
      }

      const res = await createConsultationNote(payload)
      setExistingNote(res)
      setSuccessMsg('Clinical consultation record and digital prescriptions successfully documented!')
      onSaved(res)
    } catch (err) {
      setError(err.message || 'Failed to save clinical consultation record.')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isOpen || !appointment) return null

  const patientName = appointment.patient?.full_name || 'Patient'

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Clinical Consultation & EHR Record"
      size="xl"
    >
      <ModalHeader onClose={onClose}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold text-teal-700 uppercase tracking-wider">
                Clinical Encounter
              </span>
              <Badge variant={existingNote ? 'success' : 'teal'} size="xs">
                {existingNote ? 'Documented Record' : 'New Clinical Entry'}
              </Badge>
            </div>
            <h3 className="text-base sm:text-lg font-extrabold text-brand-text">
              Consultation: {patientName}
            </h3>
          </div>
          <div className="text-right text-xs text-brand-muted">
            <span className="font-mono font-bold text-brand-text block">
              Ref: {appointment.appointment_token}
            </span>
            <span>Date: {appointment.appointment_date}</span>
          </div>
        </div>
      </ModalHeader>

      <ModalBody className="space-y-4">
        {/* Navigation Tabs */}
        <div className="flex items-center border-b border-brand-border/80 gap-1 pb-1">
          <button
            type="button"
            onClick={() => setActiveTab('notes')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all cursor-pointer ${
              activeTab === 'notes'
                ? 'bg-brand-primary text-white shadow-xs'
                : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
            }`}
          >
            Clinical Notes &amp; Diagnosis
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('prescriptions')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'prescriptions'
                ? 'bg-brand-primary text-white shadow-xs'
                : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
            }`}
          >
            <span>Digital Prescriptions</span>
            {rxItems.some((it) => it.medication_name.trim()) && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('followup')}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'followup'
                ? 'bg-brand-primary text-white shadow-xs'
                : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
            }`}
          >
            <span>Follow-Up Care</span>
            {followUpDate && <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />}
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('assistant')
              if (!cdssData && !isCdssLoading) {
                runCDSSAnalysis()
              }
            }}
            className={`px-3.5 py-1.5 text-xs font-bold rounded-xl transition-all cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'assistant'
                ? 'bg-teal-700 text-white shadow-xs'
                : 'text-teal-700 hover:text-teal-900 hover:bg-teal-50'
            }`}
          >
            <ClinicalIcon name="sparkles" size={13} className={activeTab === 'assistant' ? 'text-teal-200' : 'text-teal-600'} />
            <span>AI Clinical Assistant</span>
            {cdssData?.medication_safety?.overall_safety_status === 'WARNING_FLAGGED' ? (
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" title="Medication warning flagged" />
            ) : cdssData ? (
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
            ) : null}
          </button>
        </div>

        {/* Loading Spinner */}
        {isLoading && (
          <div className="py-8 space-y-3">
            <Skeleton className="h-4 w-1/3 rounded-md" />
            <Skeleton className="h-24 w-full rounded-2xl" />
          </div>
        )}

        {/* Feedback alerts */}
        {error && (
          <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={16} className="text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-2">
            <ClinicalIcon name="check" size={16} className="text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {!isLoading && (
          <form id="consultation-form" onSubmit={handleSubmit} className="space-y-4">
            {/* TAB 1: Clinical Notes & Diagnosis */}
            {activeTab === 'notes' && (
              <div className="space-y-4 text-xs">
                {/* Chief Complaint */}
                <div className="space-y-1">
                  <label className="font-bold text-brand-text flex items-center gap-1">
                    <span>Chief Complaint</span>
                    <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={chiefComplaint}
                    onChange={(e) => setChiefComplaint(e.target.value)}
                    placeholder="Patient's primary presenting symptom or clinical reason for visit..."
                    className="w-full p-2.5 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                    required
                  />
                </div>

                {/* Symptoms & Physical Exam Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-bold text-brand-text">Reported Symptoms</label>
                    <textarea
                      rows={2}
                      value={symptoms}
                      onChange={(e) => setSymptoms(e.target.value)}
                      placeholder="Duration, intensity, onset, aggravating/relieving factors..."
                      className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-bold text-brand-text">Examination &amp; Vitals</label>
                    <textarea
                      rows={2}
                      value={examinationNotes}
                      onChange={(e) => setExaminationNotes(e.target.value)}
                      placeholder="Blood pressure, heart rate, physical examination findings..."
                      className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                    />
                  </div>
                </div>

                {/* Clinical Observations */}
                <div className="space-y-1">
                  <label className="font-bold text-brand-text">Objective Clinical Observations</label>
                  <textarea
                    rows={2}
                    value={clinicalObservations}
                    onChange={(e) => setClinicalObservations(e.target.value)}
                    placeholder="Physician's assessment of general condition, laboratory results, or diagnostics..."
                    className="w-full p-2.5 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                  />
                </div>

                {/* Structured Diagnosis Section */}
                <div className="p-3.5 rounded-2xl bg-brand-ground border border-brand-border space-y-2.5">
                  <div className="flex items-center gap-1.5">
                    <ClinicalIcon name="activity" size={14} className="text-brand-primary" />
                    <span className="font-bold text-brand-text uppercase tracking-wider text-[11px]">
                      Clinician Diagnosis
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                    <div className="sm:col-span-2 space-y-1">
                      <label className="font-semibold text-brand-text text-[11px]">Diagnosis Name</label>
                      <input
                        type="text"
                        value={diagnosisName}
                        onChange={(e) => setDiagnosisName(e.target.value)}
                        placeholder="e.g. Essential Primary Hypertension"
                        className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent/50"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="font-semibold text-brand-text text-[11px]">Standard Code (e.g. ICD-10)</label>
                      <input
                        type="text"
                        value={diagnosisCode}
                        onChange={(e) => setDiagnosisCode(e.target.value)}
                        placeholder="e.g. ICD-10 I10"
                        className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent/50"
                      />
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="font-bold text-brand-text flex items-center gap-1">
                      <span>Diagnostic Impression Summary</span>
                      <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      rows={2}
                      value={diagnosisSummary}
                      onChange={(e) => setDiagnosisSummary(e.target.value)}
                      placeholder="Comprehensive diagnostic conclusion..."
                      className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                      required
                    />
                  </div>
                </div>

                {/* Treatment Plan & Recommendations */}
                <div className="space-y-1">
                  <label className="font-bold text-brand-text flex items-center gap-1">
                    <span>Treatment &amp; Management Plan</span>
                    <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={treatmentPlan}
                    onChange={(e) => setTreatmentPlan(e.target.value)}
                    placeholder="Pharmacological therapy, diagnostic workup, lifestyle adjustments..."
                    className="w-full p-2.5 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-brand-text">Doctor's Lifestyle &amp; Dietary Advice</label>
                  <textarea
                    rows={2}
                    value={doctorRecommendations}
                    onChange={(e) => setDoctorRecommendations(e.target.value)}
                    placeholder="Physical activity guidelines, dietary sodium restriction, warning signs to watch for..."
                    className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text"
                  />
                </div>
              </div>
            )}

            {/* TAB 2: Digital Prescriptions */}
            {activeTab === 'prescriptions' && (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-brand-text uppercase tracking-wider text-[11px]">
                      Digital Prescription Items
                    </h4>
                    <p className="text-[10px] text-brand-muted">
                      Issued with unique tamper-evident verification token and stored in the patient's EHR
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="xs"
                    variant="outline"
                    onClick={handleAddRxItem}
                    className="text-xs cursor-pointer"
                  >
                    + Add Medication
                  </Button>
                </div>

                {/* Active Issued Prescription & Immutability Alert */}
                {existingNote?.prescriptions?.some((rx) => rx.is_active) && (
                  <div className="p-3.5 rounded-2xl bg-indigo-50 border border-indigo-200/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-950 text-[11px] flex items-center gap-1.5">
                        <ClinicalIcon name="shield-check" size={13} className="text-indigo-600" />
                        Issued Rx: {existingNote.prescriptions.find((rx) => rx.is_active)?.prescription_number}
                      </span>
                      <Badge variant="info" size="xs">
                        Revision v{existingNote.prescriptions.find((rx) => rx.is_active)?.version || 1}
                      </Badge>
                    </div>
                    <p className="text-[10px] text-indigo-800 leading-relaxed">
                      Issued prescriptions are tamper-evident and legally immutable. To revise medications or dosages, enter your clinical amendment rationale below.
                    </p>
                    <div className="space-y-1 pt-1">
                      <label className="text-[10px] font-bold text-indigo-950 uppercase tracking-wider block">
                        Clinical Amendment Rationale (Required to revise issued Rx)
                      </label>
                      <input
                        type="text"
                        value={amendmentReason}
                        onChange={(e) => setAmendmentReason(e.target.value)}
                        placeholder="e.g. Dose adjusted to 250mg due to mild nausea, or modified duration"
                        className="w-full p-2 rounded-xl border border-indigo-200 bg-white text-brand-text text-xs focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      />
                    </div>
                  </div>
                )}

                {/* Medication Items List */}
                <div className="space-y-3">
                  {rxItems.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-2xl bg-brand-ground border border-brand-border space-y-2 relative"
                    >
                      <div className="flex items-center justify-between pb-1 border-b border-brand-border/60">
                        <span className="font-bold text-brand-text text-[11px]">
                          Medication #{idx + 1}
                        </span>
                        {rxItems.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveRxItem(idx)}
                            className="text-rose-500 hover:text-rose-700 text-xs font-semibold cursor-pointer"
                          >
                            Remove
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <div className="sm:col-span-2 space-y-0.5">
                          <label className="text-[10px] font-semibold text-brand-muted">Medication Name</label>
                          <input
                            type="text"
                            value={item.medication_name}
                            onChange={(e) => handleRxItemChange(idx, 'medication_name', e.target.value)}
                            placeholder="e.g. Amoxicillin, Lisinopril, Metformin"
                            className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                          />
                        </div>
                        <div className="space-y-0.5">
                          <label className="text-[10px] font-semibold text-brand-muted">Dosage</label>
                          <input
                            type="text"
                            value={item.dosage}
                            onChange={(e) => handleRxItemChange(idx, 'dosage', e.target.value)}
                            placeholder="e.g. 500mg, 10ml"
                            className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <div className="space-y-0.5">
                          <label className="text-[10px] font-semibold text-brand-muted">Frequency</label>
                          <input
                            type="text"
                            value={item.frequency}
                            onChange={(e) => handleRxItemChange(idx, 'frequency', e.target.value)}
                            placeholder="e.g. Twice daily after meals"
                            className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                          />
                        </div>
                        <div className="space-y-0.5">
                          <label className="text-[10px] font-semibold text-brand-muted">Duration</label>
                          <input
                            type="text"
                            value={item.duration}
                            onChange={(e) => handleRxItemChange(idx, 'duration', e.target.value)}
                            placeholder="e.g. 7 days, 1 month"
                            className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                          />
                        </div>
                        <div className="space-y-0.5">
                          <label className="text-[10px] font-semibold text-brand-muted">Route</label>
                          <select
                            value={item.route}
                            onChange={(e) => handleRxItemChange(idx, 'route', e.target.value)}
                            className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs cursor-pointer"
                          >
                            <option value="Oral">Oral</option>
                            <option value="Topical">Topical</option>
                            <option value="Inhalation">Inhalation</option>
                            <option value="Intravenous">Intravenous (IV)</option>
                            <option value="Sublingual">Sublingual</option>
                            <option value="Ophthalmic">Ophthalmic</option>
                          </select>
                        </div>
                      </div>

                      <div className="space-y-0.5">
                        <label className="text-[10px] font-semibold text-brand-muted">Special Administration Instructions</label>
                        <input
                          type="text"
                          value={item.instructions}
                          onChange={(e) => handleRxItemChange(idx, 'instructions', e.target.value)}
                          placeholder="e.g. Avoid dairy within 2 hours of dose. Complete full antibiotic course."
                          className="w-full p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-brand-text">General Prescription Notes &amp; Precautions</label>
                  <textarea
                    rows={2}
                    value={prescriptionNotes}
                    onChange={(e) => setPrescriptionNotes(e.target.value)}
                    placeholder="General drug interaction warnings, storage conditions, or refill guidelines..."
                    className="w-full p-2.5 rounded-xl border border-brand-border bg-brand-surface text-brand-text"
                  />
                </div>
              </div>
            )}

            {/* TAB 3: Follow-Up Care */}
            {activeTab === 'followup' && (
              <div className="space-y-4 text-xs">
                <div className="p-3.5 rounded-2xl bg-brand-ground border border-brand-border space-y-3">
                  <div className="flex items-center gap-1.5">
                    <ClinicalIcon name="calendar" size={15} className="text-brand-primary" />
                    <span className="font-bold text-brand-text uppercase tracking-wider text-[11px]">
                      Follow-Up Planning &amp; Patient Notification
                    </span>
                  </div>
                  <p className="text-[11px] text-brand-muted">
                    Setting a follow-up date automatically dispatches an in-app care reminder to the patient.
                  </p>

                  <div className="space-y-1">
                    <label className="font-bold text-brand-text">Recommended Next Visit Date</label>
                    <input
                      type="date"
                      value={followUpDate}
                      onChange={(e) => setFollowUpDate(e.target.value)}
                      min={todayStr}
                      className="p-2 rounded-xl border border-brand-border bg-brand-surface text-brand-text text-xs"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="font-bold text-brand-text">Follow-Up Instructions for Patient</label>
                    <textarea
                      rows={3}
                      value={followUpInstructions}
                      onChange={(e) => setFollowUpInstructions(e.target.value)}
                      placeholder="e.g. Repeat fasting blood glucose panel 3 days prior. Bring home blood pressure log."
                      className="w-full p-2.5 rounded-xl border border-brand-border bg-brand-surface text-brand-text"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: AI Clinical Assistant (CDSS) */}
            {activeTab === 'assistant' && (
              <div className="space-y-4 text-xs">
                {/* Assistant Controls & Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-2xl bg-teal-50/70 border border-teal-200/80">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-xl bg-teal-700 text-white flex items-center justify-center shadow-xs">
                      <ClinicalIcon name="sparkles" size={15} />
                    </div>
                    <div>
                      <h4 className="font-extrabold text-teal-950 text-xs flex items-center gap-1.5">
                        Clinical Decision Support (CDSS)
                        <Badge variant="teal" size="xs">Assistive Intelligence</Badge>
                      </h4>
                      <p className="text-[11px] text-teal-800">
                        Evidence-based note synthesis, documentation audit, Rx safety checks, and clinical practice guidelines.
                      </p>
                    </div>
                  </div>

                  <Button
                    type="button"
                    variant="primary"
                    size="xs"
                    onClick={runCDSSAnalysis}
                    disabled={isCdssLoading}
                    className="cursor-pointer shrink-0"
                  >
                    <ClinicalIcon name="sparkles" size={12} className="mr-1" />
                    {isCdssLoading ? 'Evaluating...' : 'Refresh AI Analysis'}
                  </Button>
                </div>

                {/* Prominent Safety & Governance Disclaimer */}
                <div className="p-3 rounded-xl bg-amber-50/90 border border-amber-200 text-amber-900 text-[11px] flex items-start gap-2">
                  <ClinicalIcon name="alert-triangle" size={15} className="text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">CLINICAL ASSISTIVE NOTICE: </span>
                    This decision support tool synthesizes documented clinical records and verified pharmacology rules. It does not provide autonomous diagnoses, prescribe medication, or replace professional clinical judgment. All suggestions must be reviewed and verified by the attending physician.
                  </div>
                </div>

                {/* Sub-navigation Filters */}
                <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px]">
                  {[
                    { id: 'all', label: 'All Insights' },
                    { id: 'xai', label: 'Explainable AI (XAI)' },
                    { id: 'summary', label: 'Encounter Summary' },
                    { id: 'completeness', label: 'Documentation Audit' },
                    { id: 'safety', label: 'Medication Safety' },
                    { id: 'guidelines', label: 'Clinical Guidelines' },
                    { id: 'history', label: 'Patient History' },
                  ].map((sub) => (
                    <button
                      key={sub.id}
                      type="button"
                      onClick={() => setCdssSubTab(sub.id)}
                      className={`px-2.5 py-1 rounded-lg font-bold transition-all cursor-pointer whitespace-nowrap ${
                        cdssSubTab === sub.id
                          ? 'bg-teal-800 text-white shadow-xs'
                          : 'bg-brand-surface text-brand-muted hover:text-brand-text border border-brand-border'
                      }`}
                    >
                      {sub.label}
                    </button>
                  ))}
                </div>

                {/* Loading State */}
                {isCdssLoading && (
                  <div className="p-6 rounded-2xl bg-brand-surface border border-brand-border text-center space-y-3">
                    <div className="inline-block animate-spin text-teal-700">
                      <ClinicalIcon name="sparkles" size={24} />
                    </div>
                    <p className="font-bold text-brand-text text-xs">
                      Evaluating encounter notes, pharmacology safety rules, and accredited clinical guidelines...
                    </p>
                    <p className="text-[11px] text-brand-muted max-w-md mx-auto">
                      Running 100% in-process privacy-preserving inference. Zero medical data is transmitted to external providers.
                    </p>
                  </div>
                )}

                {/* Error State */}
                {cdssError && !isCdssLoading && (
                  <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <ClinicalIcon name="alert-circle" size={16} className="text-rose-600 shrink-0" />
                      <span>{cdssError}</span>
                    </div>
                    <Button type="button" variant="outline" size="xs" onClick={runCDSSAnalysis}>
                      Retry Analysis
                    </Button>
                  </div>
                )}

                {/* Evaluated CDSS Results */}
                {cdssData && !isCdssLoading && (
                  <div className="space-y-4">
                    {/* SECTION 1: Note Summary & Structured Symptoms */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'summary') && cdssData.summary && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="file-text" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Clinical Encounter Synthesis
                            </h5>
                          </div>
                          <Badge variant="teal" size="xs">AI-Assisted Summary</Badge>
                        </div>

                        <div className="p-3 rounded-xl bg-teal-50/50 border border-teal-100/80 text-teal-950 text-xs leading-relaxed">
                          <p className="font-semibold">{cdssData.summary.executive_summary}</p>
                        </div>

                        {/* Contradiction & Discordance Alerts */}
                        {cdssData.summary.contradictions_detected?.length > 0 && (
                          <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-950 space-y-1 text-[11px]">
                            <div className="flex items-center gap-1.5 font-bold text-amber-900">
                              <ClinicalIcon name="alert-triangle" size={14} className="text-amber-600 shrink-0" />
                              <span>Documentation Discordance / Clinical Contradiction Detected:</span>
                            </div>
                            <ul className="list-disc list-inside space-y-0.5 text-[10px] text-amber-900 ml-1">
                              {cdssData.summary.contradictions_detected.map((contra, idx) => (
                                <li key={idx}>{contra}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Family History Isolation Block (Phase 11.2) */}
                        {cdssData.summary.family_history_notes?.length > 0 && (
                          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-200 space-y-1 text-[11px]">
                            <div className="flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-200">
                              <ClinicalIcon name="users" size={14} className="text-slate-600 shrink-0" />
                              <span>Documented Family History (Isolated from Acute Presentation):</span>
                            </div>
                            <ul className="list-disc list-inside space-y-0.5 text-[10px] text-slate-700 dark:text-slate-300 ml-1">
                              {cdssData.summary.family_history_notes.map((fh, idx) => (
                                <li key={idx}>{fh}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Clinical Diagnostic Uncertainty Block (Phase 11.2) */}
                        {cdssData.summary.uncertain_statements?.length > 0 && (
                          <div className="p-3 rounded-xl bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 text-purple-950 dark:text-purple-200 space-y-1 text-[11px]">
                            <div className="flex items-center gap-1.5 font-bold text-purple-900 dark:text-purple-200">
                              <ClinicalIcon name="help-circle" size={14} className="text-purple-600 shrink-0" />
                              <span>Clinical Diagnostic Uncertainty / Suspected Hypotheses:</span>
                            </div>
                            <ul className="list-disc list-inside space-y-0.5 text-[10px] text-purple-900 dark:text-purple-300 ml-1">
                              {cdssData.summary.uncertain_statements.map((u, idx) => (
                                <li key={idx}>{u}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Conditional Directives Block (Phase 11.2) */}
                        {cdssData.summary.conditional_directives?.length > 0 && (
                          <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-950 dark:text-blue-200 space-y-1 text-[11px]">
                            <div className="flex items-center gap-1.5 font-bold text-blue-900 dark:text-blue-200">
                              <ClinicalIcon name="info" size={14} className="text-blue-600 shrink-0" />
                              <span>Contingency Directives & Conditional Plans:</span>
                            </div>
                            <ul className="list-disc list-inside space-y-0.5 text-[10px] text-blue-900 dark:text-blue-300 ml-1">
                              {cdssData.summary.conditional_directives.map((cd, idx) => (
                                <li key={idx}>{cd}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Structured Symptoms */}
                        <div className="space-y-1.5">
                          <span className="font-bold text-brand-text text-[11px]">Extracted Symptoms (Documented in Notes):</span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {cdssData.summary.structured_symptoms?.map((s, idx) => (
                              <div key={idx} className="p-2 rounded-xl bg-brand-ground border border-brand-border text-[11px] flex items-center justify-between gap-2">
                                <div>
                                  <div className="flex items-center gap-1 flex-wrap">
                                    <span className="font-bold text-brand-text block">{s.symptom_name}</span>
                                    {s.source_attribution === 'HISTORICAL_RECORD' && (
                                      <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 text-[9px] font-medium">Historical</span>
                                    )}
                                    {(s.is_uncertain || s.certainty === 'SUSPECTED') && (
                                      <span className="px-1.5 py-0.2 rounded bg-purple-100 text-purple-800 text-[9px] font-medium">Suspected</span>
                                    )}
                                    {s.is_family_history && (
                                      <span className="px-1.5 py-0.2 rounded bg-slate-200 text-slate-800 text-[9px] font-medium">Family History</span>
                                    )}
                                  </div>
                                  {s.duration_onset && (
                                    <span className="text-brand-muted text-[10px]">Onset: {s.duration_onset}</span>
                                  )}
                                </div>
                                <div className="text-right shrink-0">
                                  <Badge
                                    variant={s.severity_assessment === 'Severe' ? 'danger' : s.severity_assessment === 'Moderate' ? 'warning' : 'outline'}
                                    size="xs"
                                  >
                                    {s.severity_assessment}
                                  </Badge>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Pertinent Negatives (Explicitly Denied Symptoms) */}
                          {cdssData.summary.pertinent_negatives?.length > 0 && (
                            <div className="space-y-1 pt-1.5 border-t border-brand-border/40">
                              <span className="font-bold text-brand-muted text-[10px] uppercase tracking-wider block">
                                Pertinent Negatives (Explicitly Denied / Ruled Out):
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {cdssData.summary.pertinent_negatives.map((neg, idx) => (
                                  <span
                                    key={idx}
                                    className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-[10px] flex items-center gap-1 line-through"
                                  >
                                    <ClinicalIcon name="check" size={10} className="text-slate-400 no-underline" />
                                    {neg}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="flex justify-end pt-1">
                          <Button
                            type="button"
                            variant="outline"
                            size="xs"
                            onClick={() => {
                              const text = cdssData.summary.executive_summary
                              setDiagnosisSummary((prev) => (prev ? `${prev}\n\n[Clinical Summary]: ${text}` : text))
                              setActiveTab('notes')
                            }}
                            className="text-[11px] cursor-pointer"
                          >
                            Copy Summary to Diagnosis Field
                          </Button>
                        </div>
                      </div>
                    )}

                                        {/* SECTION: Explainable AI (XAI) Recommendations (Phase 11.3) */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'xai') && cdssData.explainable_recommendations?.length > 0 && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="cpu" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Explainable AI (XAI) Clinical Recommendations
                            </h5>
                          </div>
                          <Badge variant="teal" size="xs">
                            {cdssData.explainable_recommendations.length} Active Insights
                          </Badge>
                        </div>

                        <div className="space-y-3">
                          {cdssData.explainable_recommendations.map((rec) => (
                            <div
                              key={rec.recommendation_id}
                              className="p-3.5 rounded-xl bg-slate-50/70 border border-slate-200 text-xs space-y-2.5 hover:border-teal-300 transition-all"
                            >
                              <div className="flex items-start justify-between gap-2 flex-wrap">
                                <div>
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span className="font-bold text-slate-900 text-xs sm:text-sm">
                                      {rec.recommendation_summary}
                                    </span>
                                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-50 text-teal-800 font-bold border border-teal-200">
                                      {rec.domain}
                                    </span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-1.5 shrink-0">
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                    rec.certainty_level === 'HIGH_CONFIDENCE_FACT'
                                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                      : rec.certainty_level === 'MODERATE_CLINICAL_HYPOTHESIS'
                                      ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                      : 'bg-indigo-100 text-indigo-800 border border-indigo-300'
                                  }`}>
                                    {rec.certainty_level.replace(/_/g, ' ')}
                                  </span>
                                  <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-900 font-bold text-[10px]">
                                    {Math.round(rec.confidence_score * 100)}% Conf
                                  </span>
                                </div>
                              </div>

                              <p className="text-slate-700 leading-relaxed text-[11px]">
                                {rec.clinical_reasoning}
                              </p>

                              {/* Structured Evidence Breakdown */}
                              {rec.evidence_breakdown && (
                                <div className="p-2.5 rounded-lg bg-white border border-slate-200/80 space-y-2 text-[11px]">
                                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                                    Evidence Breakdown & Provenance:
                                  </div>
                                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    {/* Clinical Facts */}
                                    <div className="p-2 rounded bg-emerald-50/60 border border-emerald-100">
                                      <span className="text-[10px] font-bold text-emerald-900 block mb-1">
                                        ✓ Clinical Facts (Observed):
                                      </span>
                                      {rec.evidence_breakdown.clinical_facts?.length > 0 ? (
                                        <ul className="list-disc list-inside text-[10px] text-emerald-800 space-y-0.5">
                                          {rec.evidence_breakdown.clinical_facts.map((fact, fIdx) => (
                                            <li key={fIdx}>{fact}</li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <span className="text-[10px] text-slate-400 italic">None documented</span>
                                      )}
                                    </div>

                                    {/* Suspected Conditions */}
                                    <div className="p-2 rounded bg-amber-50/60 border border-amber-100">
                                      <span className="text-[10px] font-bold text-amber-900 block mb-1">
                                        ? Suspected Conditions:
                                      </span>
                                      {rec.evidence_breakdown.suspected_conditions?.length > 0 ? (
                                        <ul className="list-disc list-inside text-[10px] text-amber-800 space-y-0.5">
                                          {rec.evidence_breakdown.suspected_conditions.map((sc, scIdx) => (
                                            <li key={scIdx}>{sc}</li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <span className="text-[10px] text-slate-400 italic">None active</span>
                                      )}
                                    </div>

                                    {/* Algorithmic Predictions */}
                                    <div className="p-2 rounded bg-indigo-50/60 border border-indigo-100">
                                      <span className="text-[10px] font-bold text-indigo-900 block mb-1">
                                        ⚙ Algorithmic Predictions:
                                      </span>
                                      {rec.evidence_breakdown.algorithmic_predictions?.length > 0 ? (
                                        <ul className="list-disc list-inside text-[10px] text-indigo-800 space-y-0.5">
                                          {rec.evidence_breakdown.algorithmic_predictions.map((pred, pIdx) => (
                                            <li key={pIdx}>{pred}</li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <span className="text-[10px] text-slate-400 italic">None generated</span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              )}

                              {/* Risk Factors and Rules */}
                              <div className="flex flex-wrap items-center justify-between gap-1.5 text-[10px] text-slate-500 pt-1 border-t border-slate-200/60">
                                <div className="flex items-center gap-1 flex-wrap">
                                  {rec.supporting_rules?.map((rule, rIdx) => (
                                    <span key={rIdx} className="font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-700">
                                      {rule}
                                    </span>
                                  ))}
                                  <span className="px-1.5 py-0.2 rounded bg-teal-50 text-teal-800 font-bold">
                                    {rec.evidence_classification}
                                  </span>
                                </div>
                                <span>KB Version: {rec.kb_version}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* SECTION 2: Documentation Completeness Audit */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'completeness') && cdssData.documentation_completeness && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="shield-check" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Documentation Completeness Review
                            </h5>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-extrabold text-brand-text text-xs">
                              Score: {cdssData.documentation_completeness.completeness_score}%
                            </span>
                            <Badge
                              variant={
                                cdssData.documentation_completeness.overall_status === 'optimal'
                                  ? 'success'
                                  : cdssData.documentation_completeness.overall_status === 'acceptable'
                                  ? 'warning'
                                  : 'danger'
                              }
                              size="xs"
                            >
                              {cdssData.documentation_completeness.overall_status.toUpperCase()}
                            </Badge>
                          </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full bg-brand-ground rounded-full h-2 overflow-hidden border border-brand-border">
                          <div
                            className={`h-full transition-all duration-500 ${
                              cdssData.documentation_completeness.completeness_score >= 80
                                ? 'bg-emerald-600'
                                : cdssData.documentation_completeness.completeness_score >= 50
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                            style={{ width: `${cdssData.documentation_completeness.completeness_score}%` }}
                          />
                        </div>

                        {/* Checklist */}
                        <div className="space-y-1.5">
                          {cdssData.documentation_completeness.items?.map((item, idx) => (
                            <div
                              key={idx}
                              className={`p-2 rounded-xl border text-[11px] flex items-start gap-2 ${
                                item.is_complete
                                  ? 'bg-emerald-50/40 border-emerald-200/60 text-emerald-950'
                                  : item.status === 'warning'
                                  ? 'bg-amber-50/40 border-amber-200/60 text-amber-950'
                                  : 'bg-rose-50/40 border-rose-200/60 text-rose-950'
                              }`}
                            >
                              <div className="shrink-0 mt-0.5">
                                {item.is_complete ? (
                                  <ClinicalIcon name="check" size={13} className="text-emerald-700" />
                                ) : (
                                  <ClinicalIcon name="alert-triangle" size={13} className={item.status === 'warning' ? 'text-amber-600' : 'text-rose-600'} />
                                )}
                              </div>
                              <div className="flex-1">
                                <span className="font-bold">{item.section}: </span>
                                <span>{item.message}</span>
                                {item.recommendation && (
                                  <span className="block text-[10px] text-brand-muted mt-0.5">
                                    Tip: {item.recommendation}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* SECTION 3: Medication Safety Support */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'safety') && cdssData.medication_safety && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="pill" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Medication Safety &amp; Interaction Audit
                            </h5>
                          </div>
                          <Badge
                            variant={
                              cdssData.medication_safety.overall_safety_status === 'SAFE'
                                ? 'success'
                                : cdssData.medication_safety.overall_safety_status === 'REVIEW_RECOMMENDED'
                                ? 'warning'
                                : 'danger'
                            }
                            size="xs"
                          >
                            {cdssData.medication_safety.overall_safety_status}
                          </Badge>
                        </div>

                        {/* Allergy Documentation Safety Warning Banner (Phase 11.2) */}
                        {(cdssData.medication_safety.allergy_safety_warning || cdssData.patient_insights?.allergy_safety_warning) && (
                          <div className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs ${
                            (cdssData.medication_safety.allergy_documentation_status === 'NOT_DOCUMENTED' ||
                             cdssData.patient_insights?.allergy_documentation_status === 'NOT_DOCUMENTED')
                              ? 'bg-rose-50 border-rose-300 text-rose-950 dark:bg-rose-950/30 dark:border-rose-800 dark:text-rose-200'
                              : (cdssData.medication_safety.allergy_documentation_status === 'REQUIRES_VERIFICATION' ||
                                 cdssData.patient_insights?.allergy_documentation_status === 'REQUIRES_VERIFICATION')
                              ? 'bg-amber-50 border-amber-300 text-amber-950 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200'
                              : 'bg-emerald-50 border-emerald-300 text-emerald-950 dark:bg-emerald-950/30 dark:border-emerald-800 dark:text-emerald-200'
                          }`}>
                            <ClinicalIcon name="alert-triangle" size={16} className={`shrink-0 mt-0.5 ${
                              (cdssData.medication_safety.allergy_documentation_status === 'NOT_DOCUMENTED' ||
                               cdssData.patient_insights?.allergy_documentation_status === 'NOT_DOCUMENTED')
                                ? 'text-rose-600'
                                : 'text-amber-600'
                            }`} />
                            <div className="flex-1 space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-extrabold tracking-wide uppercase text-[11px]">
                                  Allergy Status: {
                                    cdssData.medication_safety.allergy_documentation_status ||
                                    cdssData.patient_insights?.allergy_documentation_status
                                  }
                                </span>
                                <Badge
                                  variant={
                                    (cdssData.medication_safety.allergy_documentation_status === 'NOT_DOCUMENTED' ||
                                     cdssData.patient_insights?.allergy_documentation_status === 'NOT_DOCUMENTED')
                                      ? 'danger'
                                      : 'warning'
                                  }
                                  size="xs"
                                >
                                  Safety Mandate
                                </Badge>
                              </div>
                              <p className="font-medium text-[11px] leading-snug">
                                {cdssData.medication_safety.allergy_safety_warning || cdssData.patient_insights?.allergy_safety_warning}
                              </p>
                            </div>
                          </div>
                        )}

                                                {/* Absolute Clinical Contraindications (Phase 11.3) */}
                        {cdssData.medication_safety.contraindication_alerts?.length > 0 && (
                          <div className="space-y-2">
                            <div className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full bg-rose-600 animate-pulse" />
                              <span className="font-extrabold text-rose-900 text-xs">
                                CRITICAL: Absolute Clinical Contraindications Detected ({cdssData.medication_safety.contraindication_alerts.length}):
                              </span>
                            </div>
                            {cdssData.medication_safety.contraindication_alerts.map((ci, idx) => (
                              <div key={idx} className="p-3.5 rounded-xl bg-rose-100/70 border-2 border-rose-400 text-rose-950 space-y-2 text-[11px] shadow-xs">
                                <div className="flex items-center justify-between flex-wrap gap-1">
                                  <div className="flex items-center gap-2">
                                    <span className="font-extrabold text-xs text-rose-950">
                                      {ci.medication_name} is Contraindicated in {ci.contraindicated_condition}
                                    </span>
                                    <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-rose-200 text-rose-900 font-bold">
                                      {ci.rule_id}
                                    </span>
                                  </div>
                                  <Badge variant="danger" size="xs">
                                    ABSOLUTE CONTRAINDICATION
                                  </Badge>
                                </div>

                                <p className="font-medium text-rose-900 leading-snug">
                                  <span className="font-bold">Clinical Hazard: </span>{ci.clinical_risk}
                                </p>
                                <p className="text-rose-950 font-bold bg-white/80 p-2 rounded-lg border border-rose-300">
                                  Mandated Clinician Action: {ci.recommended_action}
                                </p>

                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[10px] text-rose-800 pt-1 border-t border-rose-200">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span>Evidence: <strong className="font-semibold">{ci.evidence_source}</strong></span>
                                    <span className="px-1.5 py-0.2 rounded bg-rose-200 text-rose-900 font-bold text-[9px]">
                                      {ci.evidence_class}
                                    </span>
                                    {ci.evidence_url && (
                                      <a
                                        href={ci.evidence_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-teal-900 underline font-bold"
                                      >
                                        Source ↗
                                      </a>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {acknowledgedAlerts[ci.rule_id] ? (
                                      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-md">
                                        <ClinicalIcon name="check" size={11} />
                                        {acknowledgedAlerts[ci.rule_id].action === 'ACKNOWLEDGE'
                                          ? 'Acknowledged'
                                          : `Dismissed (${acknowledgedAlerts[ci.rule_id].reason})`}
                                      </span>
                                    ) : (
                                      <>
                                        <Button
                                          type="button"
                                          size="xs"
                                          variant="outline"
                                          className="text-[10px] h-6 px-2 text-rose-900 border-rose-300 hover:bg-rose-100 cursor-pointer"
                                          onClick={() => handleAcknowledgeAlert(ci)}
                                        >
                                          <ClinicalIcon name="check" size={10} className="mr-1" />
                                          Acknowledge
                                        </Button>
                                        <Button
                                          type="button"
                                          size="xs"
                                          variant="outline"
                                          className="text-[10px] h-6 px-2 text-slate-700 border-slate-300 hover:bg-slate-100 cursor-pointer"
                                          onClick={() => {
                                            setDismissModalRule(ci)
                                            setDismissReasonInput('')
                                          }}
                                        >
                                          Dismiss (Reason)
                                        </Button>
                                      </>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Verified Drug Interactions */}
                        {cdssData.medication_safety.interaction_alerts?.length > 0 ? (
                          <div className="space-y-2">
                            <span className="font-bold text-rose-900 text-[11px]">
                              High-Risk Drug-Drug Interactions Detected ({cdssData.medication_safety.interaction_alerts.length}):
                            </span>
                            {cdssData.medication_safety.interaction_alerts.map((alert, idx) => (
                              <div key={idx} className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-950 space-y-1.5 text-[11px]">
                                <div className="flex items-center justify-between flex-wrap gap-1">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-extrabold text-xs">
                                      {alert.primary_medication} + {alert.secondary_medication}
                                    </span>
                                    {alert.primary_class && alert.secondary_class && (
                                      <span className="text-[10px] text-brand-muted">
                                        ({alert.primary_class} × {alert.secondary_class})
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-1">
                                    {alert.clinical_certainty && (
                                      <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                                        alert.clinical_certainty === 'ESTABLISHED'
                                          ? 'bg-rose-200 text-rose-900'
                                          : 'bg-amber-100 text-amber-900'
                                      }`}>
                                        {alert.clinical_certainty}
                                      </span>
                                    )}
                                    <Badge variant={alert.severity === 'CRITICAL' ? 'danger' : 'warning'} size="xs">
                                      {alert.severity} SEVERITY
                                    </Badge>
                                  </div>
                                </div>
                                <p><span className="font-semibold">Mechanism:</span> {alert.clinical_mechanism}</p>
                                <p><span className="font-semibold">Clinical Risk:</span> {alert.risk_summary}</p>
                                <p className="text-rose-900 font-bold bg-white/60 p-1.5 rounded-lg border border-rose-200/60">
                                  Recommended Action: {alert.recommended_action}
                                </p>
                                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[10px] text-rose-700">
                                  <span>
                                    Evidence Source: <span className="font-semibold">{alert.evidence_source}</span>
                                    {alert.last_reviewed_date && ` (Reviewed: ${alert.last_reviewed_date})`}
                                  </span>
                                  {alert.source_url && (
                                    <a
                                      href={alert.source_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-teal-800 hover:text-teal-950 font-semibold underline text-[10px]"
                                    >
                                      <span>Authority Protocol</span>
                                      <ClinicalIcon name="external-link" size={10} />
                                    </a>
                                  )}
                                </div>

                                {/* Phase 11.2 Alert Governance & Clinician Action Controls */}
                                <div className="flex items-center justify-between pt-2 border-t border-rose-200/60 mt-1 flex-wrap gap-2">
                                  <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-rose-800">
                                    <span className="font-semibold font-mono">Rule: {alert.rule_id || alert.rule_identifier}</span>
                                    {alert.rule_version && <span>• v{alert.rule_version}</span>}
                                    {alert.evidence_classification && (
                                      <span className="px-1.5 py-0.2 rounded bg-rose-200 text-rose-900 font-bold text-[9px]">
                                        {alert.evidence_classification}
                                      </span>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {acknowledgedAlerts[alert.rule_id || alert.rule_identifier] ? (
                                      <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-md">
                                        <ClinicalIcon name="check" size={11} />
                                        {acknowledgedAlerts[alert.rule_id || alert.rule_identifier].action === 'ACKNOWLEDGE'
                                          ? 'Acknowledged'
                                          : `Dismissed (${acknowledgedAlerts[alert.rule_id || alert.rule_identifier].reason})`}
                                      </span>
                                    ) : (
                                      <>
                                        <Button
                                          type="button"
                                          size="xs"
                                          variant="outline"
                                          className="text-[10px] h-6 px-2 text-rose-900 border-rose-300 hover:bg-rose-100 cursor-pointer"
                                          onClick={() => handleAcknowledgeAlert(alert)}
                                        >
                                          <ClinicalIcon name="check" size={10} className="mr-1" />
                                          Acknowledge
                                        </Button>
                                        <Button
                                          type="button"
                                          size="xs"
                                          variant="outline"
                                          className="text-[10px] h-6 px-2 text-slate-700 border-slate-300 hover:bg-slate-100 cursor-pointer"
                                          onClick={() => {
                                            setDismissModalRule(alert)
                                            setDismissReasonInput('')
                                          }}
                                        >
                                          Dismiss (Reason)
                                        </Button>
                                      </>
                                    )}
                                    <Button
                                      type="button"
                                      size="xs"
                                      variant="ghost"
                                      className="text-[10px] h-6 px-1.5 text-teal-800 hover:bg-teal-100/50 cursor-pointer"
                                      onClick={() => {
                                        setFeedbackTarget({
                                          targetType: 'drug_interaction_rule',
                                          targetId: alert.rule_id || alert.rule_identifier,
                                          ruleId: alert.rule_id || alert.rule_identifier,
                                        })
                                        setShowFeedbackModal(true)
                                      }}
                                      title="Submit feedback on this alert"
                                    >
                                      Feedback
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-2.5 rounded-xl bg-emerald-50/50 border border-emerald-200/60 text-emerald-900 text-[11px] flex items-center gap-2">
                            <ClinicalIcon name="check" size={14} className="text-emerald-600 shrink-0" />
                            <span>No verified high-risk drug-drug interactions detected between prescribed medications.</span>
                          </div>
                        )}

                        {/* Duplicate Medication Alerts */}
                        {cdssData.medication_safety.duplicate_alerts?.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="font-bold text-amber-900 text-[11px]">Pharmacological Redundancy &amp; Duplicates:</span>
                            {cdssData.medication_safety.duplicate_alerts.map((dup, idx) => (
                              <div key={idx} className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-950 text-[11px] space-y-1">
                                <div>
                                  <span className="font-bold">{dup.medication_name}: </span>
                                  <span>{dup.message}</span>
                                </div>
                                {dup.clinical_rationale && (
                                  <p className="text-[10px] text-amber-900"><span className="font-semibold">Rationale:</span> {dup.clinical_rationale}</p>
                                )}
                                {dup.recommended_action && (
                                  <p className="text-[10px] font-semibold text-amber-950 bg-white/60 p-1 rounded border border-amber-200/50">
                                    Recommendation: {dup.recommended_action}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Missing Prescription Instructions */}
                        {cdssData.medication_safety.instruction_alerts?.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="font-bold text-brand-text text-[11px]">Incomplete Prescription Directives:</span>
                            {cdssData.medication_safety.instruction_alerts.map((ins, idx) => (
                              <div key={idx} className="p-2 rounded-xl bg-brand-ground border border-brand-border text-brand-muted text-[11px] flex items-center justify-between gap-2">
                                <div>
                                  <span className="font-bold text-brand-text">{ins.medication_name}: </span>
                                  <span>{ins.message}</span>
                                  {ins.clinical_impact && (
                                    <span className="block text-[10px] text-amber-700 mt-0.5">Impact: {ins.clinical_impact}</span>
                                  )}
                                </div>
                                {ins.severity && (
                                  <Badge variant={ins.severity === 'HIGH' ? 'danger' : 'warning'} size="xs">
                                    {ins.severity}
                                  </Badge>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        <p className="text-[10px] text-brand-muted italic">
                          {cdssData.medication_safety.verification_coverage_note}
                        </p>
                      </div>
                    )}

                    {/* SECTION 4: Evidence-Based Clinical Guidelines */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'guidelines') && cdssData.guidelines && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="stethoscope" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Accredited Clinical Practice Guidelines
                            </h5>
                          </div>
                          <Badge variant="teal" size="xs">
                            {cdssData.guidelines.total_matched} Matched
                          </Badge>
                        </div>

                        {cdssData.guidelines.matched_guidelines?.length > 0 ? (
                          <div className="space-y-3">
                            {cdssData.guidelines.matched_guidelines.map((guide) => (
                              <div key={guide.guideline_id} className="p-3 rounded-xl bg-teal-50/40 border border-teal-200/70 space-y-2 text-[11px]">
                                <div className="flex items-start justify-between gap-2">
                                  <div>
                                    <h6 className="font-extrabold text-teal-950 text-xs">{guide.guideline_title || guide.condition_name}</h6>
                                    <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-teal-800 mt-0.5">
                                      <span>{guide.publishing_authority} ({guide.publication_year})</span>
                                      <span>• Evidence: {guide.evidence_level}</span>
                                      {guide.version && <span>• v{guide.version}</span>}
                                      {guide.last_verified_date && <span>• Verified: {guide.last_verified_date}</span>}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1 shrink-0 flex-wrap">
                                    {guide.freshness_status === 'CURRENT_VERIFIED' || guide.freshness_status === 'CURRENT_VALIDATED' ? (
                                      <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold text-[9px] border border-emerald-200">
                                        ✓ CURRENT VERIFIED
                                      </span>
                                    ) : guide.freshness_status === 'REVIEW_REQUIRED' ? (
                                      <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold text-[9px] border border-amber-200">
                                        ⚠ REVIEW REQUIRED
                                      </span>
                                    ) : guide.freshness_status === 'UNDER_REVIEW' ? (
                                      <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 font-bold text-[9px] border border-purple-200">
                                        ⏳ UNDER REVIEW
                                      </span>
                                    ) : guide.freshness_status === 'SUPERSEDED' ? (
                                      <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 font-bold text-[9px] border border-rose-200">
                                        ✕ SUPERSEDED
                                      </span>
                                    ) : (
                                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 font-bold text-[9px]">
                                        UNVERIFIED
                                      </span>
                                    )}
                                    {guide.is_review_overdue && (
                                      <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 font-bold text-[9px] border border-rose-300">
                                        ⚠ OVERDUE ({Math.abs(guide.days_until_review || 0)}d)
                                      </span>
                                    )}
                                    {guide.evidence_classification && (
                                      <span className="px-1.5 py-0.5 rounded bg-teal-100 text-teal-900 font-semibold text-[9px]">
                                        {guide.evidence_classification}
                                      </span>
                                    )}
                                    <Badge variant="teal" size="xs">{guide.icd10_codes.join(', ')}</Badge>
                                  </div>
                                </div>

                                <p className="text-brand-text text-[11px] leading-relaxed">{guide.summary}</p>

                                {guide.source_url && (
                                  <div>
                                    <a
                                      href={guide.source_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-teal-800 hover:text-teal-950 font-semibold underline text-[10px]"
                                    >
                                      <span>Official Protocol ({guide.publishing_authority})</span>
                                      <ClinicalIcon name="external-link" size={10} />
                                    </a>
                                  </div>
                                )}

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                                  {guide.recommendations?.map((rec, rIdx) => (
                                    <div key={rIdx} className="p-2 rounded-lg bg-white border border-teal-100 text-[10px] space-y-1">
                                      <span className="font-bold text-teal-900 uppercase tracking-wider text-[9px] block">
                                        {rec.category}
                                      </span>
                                      <p className="text-brand-text leading-snug">{rec.text}</p>
                                    </div>
                                  ))}
                                </div>

                                <div className="p-2 rounded-lg bg-amber-50/60 border border-amber-200/60 text-[10px] text-amber-900">
                                  <span className="font-bold">Clinical Caveat: </span>{guide.uncertainty_statement}
                                </div>

                                <div className="flex justify-end pt-1">
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="xs"
                                    onClick={() => {
                                      const text = guide.recommendations?.map(r => `• ${r.category}: ${r.text}`).join('\n') || ''
                                      setTreatmentPlan((prev) => (prev ? `${prev}\n\n[Guideline Directives - ${guide.condition_name}]:\n${text}` : text))
                                      setActiveTab('notes')
                                    }}
                                    className="text-[10px] cursor-pointer"
                                  >
                                    Incorporate Directives into Treatment Plan
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-3 rounded-xl bg-brand-ground border border-brand-border text-brand-muted text-[11px] text-center">
                            No accredited clinical guidelines matched the current diagnostic search. Enter an ICD-10 code (e.g. I10, E11, G43, J45) or condition name to retrieve practice protocols.
                          </div>
                        )}
                      </div>
                    )}

                    {/* SECTION 5: Longitudinal Patient Medical History */}
                    {(cdssSubTab === 'all' || cdssSubTab === 'history') && cdssData.patient_insights && (
                      <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-3">
                        <div className="flex items-center justify-between border-b border-brand-border/60 pb-2">
                          <div className="flex items-center gap-1.5">
                            <ClinicalIcon name="heart-pulse" size={15} className="text-teal-700" />
                            <h5 className="font-extrabold text-brand-text uppercase tracking-wider text-[11px]">
                              Longitudinal Patient Health Record Insights
                            </h5>
                          </div>
                          <Badge variant="teal" size="xs">
                            {cdssData.patient_insights.total_recorded_consultations} Previous Encounters
                          </Badge>
                        </div>

                        {/* Chronic Conditions */}
                        {cdssData.patient_insights.chronic_conditions?.length > 0 && (
                          <div className="space-y-1">
                            <span className="font-bold text-brand-text text-[11px]">Documented Chronic Diagnoses:</span>
                            <div className="flex flex-wrap gap-1.5">
                              {cdssData.patient_insights.chronic_conditions.map((c, idx) => (
                                <Badge key={idx} variant="warning" size="xs">
                                  {c.diagnosis_name} {c.diagnosis_code ? `(${c.diagnosis_code})` : ''}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Active Prescriptions on File */}
                        {cdssData.patient_insights.active_prescriptions?.length > 0 ? (
                          <div className="space-y-1">
                            <span className="font-bold text-brand-text text-[11px]">Active Prescriptions on File:</span>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                              {cdssData.patient_insights.active_prescriptions.map((ap, idx) => (
                                <div key={idx} className="p-2 rounded-lg bg-brand-ground border border-brand-border text-[10px]">
                                  <span className="font-bold text-brand-text block">{ap.medication_name} {ap.dosage}</span>
                                  <span className="text-brand-muted">{ap.frequency} • Ref: {ap.prescription_number}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-[11px] text-brand-muted">No active prescriptions previously recorded in EHR history.</p>
                        )}

                        {/* Allergy Documentation Status */}
                        <div className="p-2 rounded-lg bg-brand-ground border border-brand-border text-[11px] flex items-center justify-between">
                          <span className="text-brand-muted">Documented Drug Allergies:</span>
                          <span className="font-bold text-brand-text">
                            {cdssData.patient_insights.allergy_documentation_status === 'documented' && cdssData.patient_insights.documented_allergies?.length > 0
                              ? cdssData.patient_insights.documented_allergies.join(', ')
                              : 'None Recorded in Structured Records'}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Knowledge Base Governance Footer */}
                    {cdssData.kb_metadata && (
                      <div className="p-3 rounded-2xl bg-teal-900/5 border border-teal-200/60 space-y-2 text-[10px] text-teal-950">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5 font-bold">
                              <ClinicalIcon name="shield-check" size={13} className="text-teal-700 shrink-0" />
                              <span>CDSS Knowledge Base: v{cdssData.kb_metadata.version}</span>
                              <Badge variant="teal" size="xs">Governed</Badge>
                              {cdssData.kb_metadata.governance_board && (
                                <span className="text-[9px] text-teal-800 bg-teal-100/80 px-1.5 py-0.2 rounded font-medium">
                                  {cdssData.kb_metadata.governance_board}
                                </span>
                              )}
                            </div>
                            <div className="text-teal-800">
                              Reviewed: {cdssData.kb_metadata.last_reviewed} by {cdssData.kb_metadata.clinical_reviewer} • Rules: {cdssData.kb_metadata.total_active_interaction_rules} interactions, {cdssData.kb_metadata.total_active_guidelines} guidelines • Next Review: {cdssData.kb_metadata.next_scheduled_review || '2027-06-30'}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {cdssData.kb_metadata.version_history?.length > 0 && (
                              <Button
                                type="button"
                                size="xs"
                                variant="outline"
                                className="text-[10px] h-6 px-2 text-teal-900 border-teal-300 hover:bg-teal-100/60 cursor-pointer"
                                onClick={() => setShowVersionHistory(!showVersionHistory)}
                              >
                                {showVersionHistory ? 'Hide History' : 'Version History'}
                              </Button>
                            )}
                            <Button
                              type="button"
                              size="xs"
                              variant="primary"
                              className="text-[10px] h-6 px-2 bg-teal-700 hover:bg-teal-800 text-white cursor-pointer"
                              onClick={() => {
                                setFeedbackTarget({
                                  targetType: 'cdss_encounter',
                                  targetId: appointment ? appointment.id : '',
                                  ruleId: '',
                                })
                                setShowFeedbackModal(true)
                              }}
                            >
                              Submit Feedback
                            </Button>
                          </div>
                        </div>

                        {/* Version History Drawer (Phase 11.2) */}
                        {showVersionHistory && cdssData.kb_metadata.version_history?.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-teal-200/50 space-y-1.5">
                            <span className="font-bold text-teal-950 uppercase tracking-wider text-[9px] block">
                              Knowledge Base Release Log & Governance Lineage:
                            </span>
                            <div className="space-y-1">
                              {cdssData.kb_metadata.version_history.map((vh, vIdx) => (
                                <div key={vIdx} className="p-2 rounded-lg bg-white/70 border border-teal-200/40 text-[10px] space-y-0.5">
                                  <div className="flex items-center justify-between font-bold text-teal-900">
                                    <span>v{vh.version} ({vh.release_date})</span>
                                    <span className="text-[9px] text-teal-700">{vh.approved_by}</span>
                                  </div>
                                  <p className="text-teal-950">{vh.summary_of_changes}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </form>
        )}
      </ModalBody>

      <ModalFooter>
        <div className="flex items-center justify-between w-full">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onClose}
            className="text-xs cursor-pointer"
          >
            Cancel
          </Button>

          <Button
            type="submit"
            form="consultation-form"
            variant="primary"
            size="sm"
            disabled={isSaving || isLoading}
            className="text-xs font-bold cursor-pointer"
          >
            <ClinicalIcon name="check" size={14} className="mr-1.5" />
            {isSaving ? 'Saving Consultation...' : existingNote ? 'Update Consultation EHR' : 'Complete & Save EHR'}
          </Button>
        </div>
      </ModalFooter>

      {/* Clinician Feedback Modal (Phase 11.2) */}
      <Modal
        isOpen={showFeedbackModal}
        onClose={() => {
          if (!isSubmittingFeedback) {
            setShowFeedbackModal(false)
            setFeedbackStatusMessage(null)
          }
        }}
        size="md"
      >
        <ModalHeader
          title="Clinical Decision Support Feedback"
          subtitle="Submit clinical feedback for review by the Clinical Governance Board"
          onClose={() => {
            if (!isSubmittingFeedback) {
              setShowFeedbackModal(false)
              setFeedbackStatusMessage(null)
            }
          }}
        />
        <ModalBody>
          <form id="cdss-feedback-form" onSubmit={handleSubmitFeedback} className="space-y-3.5">
            <div className="p-2.5 rounded-xl bg-teal-50 dark:bg-teal-950/30 border border-teal-200 dark:border-teal-800 text-[11px] text-teal-950 dark:text-teal-200">
              <span className="font-bold">Target: </span>
              <span>{feedbackTarget.targetType}</span>
              {feedbackTarget.ruleId && <span className="ml-1 font-mono">({feedbackTarget.ruleId})</span>}
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-brand-text">Feedback Classification</label>
              <select
                value={feedbackType}
                onChange={(e) => setFeedbackType(e.target.value)}
                className="w-full text-xs p-2 rounded-xl bg-brand-surface border border-brand-border text-brand-text focus:outline-teal-700"
              >
                <option value="RELEVANT_ALERT">RELEVANT_ALERT - High clinical relevance, confirmed</option>
                <option value="IRRELEVANT_ALERT">IRRELEVANT_ALERT - Clinically insignificant / nuisance alert</option>
                <option value="INCORRECT_ALERT">INCORRECT_ALERT - Inaccurate pharmacological rule or false positive</option>
                <option value="MISSING_INTERACTION">MISSING_INTERACTION - Expected interaction alert was missing</option>
                <option value="OUTDATED_GUIDELINE">OUTDATED_GUIDELINE - Guideline protocol is superseded or outdated</option>
                <option value="INCORRECT_SYMPTOM_EXTRACTION">INCORRECT_SYMPTOM_EXTRACTION - NLP misparsed symptom or negation</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-bold text-brand-text">Clinician Observations & Comments *</label>
              <textarea
                value={feedbackComment}
                onChange={(e) => setFeedbackComment(e.target.value)}
                placeholder="Describe why this alert was relevant, inaccurate, or how the clinical guideline should be updated..."
                rows={4}
                required
                className="w-full text-xs p-2.5 rounded-xl bg-brand-surface border border-brand-border text-brand-text placeholder-brand-muted/70 focus:outline-teal-700"
              />
            </div>

            {feedbackStatusMessage && (
              <div className={`p-2.5 rounded-xl text-xs font-medium ${
                feedbackStatusMessage.type === 'success'
                  ? 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                  : 'bg-rose-50 text-rose-900 border border-rose-200'
              }`}>
                {feedbackStatusMessage.text}
              </div>
            )}
          </form>
        </ModalBody>
        <ModalFooter>
          <div className="flex items-center justify-between w-full">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSubmittingFeedback}
              onClick={() => {
                setShowFeedbackModal(false)
                setFeedbackStatusMessage(null)
              }}
              className="text-xs cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="cdss-feedback-form"
              variant="primary"
              size="sm"
              disabled={isSubmittingFeedback || !feedbackComment.trim()}
              className="text-xs font-bold bg-teal-700 hover:bg-teal-800 text-white cursor-pointer"
            >
              {isSubmittingFeedback ? 'Submitting...' : 'Submit Feedback'}
            </Button>
          </div>
        </ModalFooter>
      </Modal>

      {/* Dismiss Alert Reason Modal (Phase 11.2) */}
      <Modal
        isOpen={Boolean(dismissModalRule)}
        onClose={() => {
          setDismissModalRule(null)
          setDismissReasonInput('')
        }}
        size="sm"
      >
        <ModalHeader
          title="Dismiss Clinical Safety Warning"
          subtitle="Document the clinical rationale for dismissing this interaction alert"
          onClose={() => {
            setDismissModalRule(null)
            setDismissReasonInput('')
          }}
        />
        <ModalBody>
          <div className="space-y-3 text-xs">
            {dismissModalRule && (
              <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 text-rose-950 dark:text-rose-200">
                <span className="font-bold">{dismissModalRule.primary_medication} + {dismissModalRule.secondary_medication}</span>
                <p className="text-[10px] mt-0.5">{dismissModalRule.risk_summary}</p>
              </div>
            )}

            <div className="space-y-1">
              <label className="block text-xs font-bold text-brand-text">Clinical Justification / Dismissal Reason *</label>
              <textarea
                value={dismissReasonInput}
                onChange={(e) => setDismissReasonInput(e.target.value)}
                placeholder="e.g. Patient previously tolerated combination; close outpatient potassium monitoring scheduled..."
                rows={3}
                required
                className="w-full text-xs p-2.5 rounded-xl bg-brand-surface border border-brand-border text-brand-text placeholder-brand-muted/70 focus:outline-teal-700"
              />
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <div className="flex items-center justify-between w-full">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setDismissModalRule(null)
                setDismissReasonInput('')
              }}
              className="text-xs cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={!dismissReasonInput.trim()}
              onClick={handleDismissAlert}
              className="text-xs font-bold bg-rose-700 hover:bg-rose-800 text-white cursor-pointer"
            >
              Confirm Dismissal
            </Button>
          </div>
        </ModalFooter>
      </Modal>
    </Modal>
  )
}

