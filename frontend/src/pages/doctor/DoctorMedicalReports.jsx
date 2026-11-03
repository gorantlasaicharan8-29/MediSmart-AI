import React, { useState, useEffect, useCallback } from 'react'
import {
  getMyAppointments,
  getMedicalReports,
  getMedicalReportAnalysis,
  getMedicalReportSummary,
  submitMedicalReportReview,
  correctMedicalParameter,
} from '../../services/api'
import {
  Button,
  Modal,
  ModalHeader,
  ModalBody,
  EmptyState,
  SkeletonCard,
  ClinicalIcon,
} from '../../components/ui'

export default function DoctorMedicalReports() {
  const [authorizedPatients, setAuthorizedPatients] = useState([])
  const [selectedPatientId, setSelectedPatientId] = useState('')
  const [patientsLoading, setPatientsLoading] = useState(true)

  // Document List State
  const [reports, setReports] = useState([])
  const [reportsLoading, setReportsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  // Document Details & Review State
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [docAnalysis, setDocAnalysis] = useState(null)
  const [docSummary, setDocSummary] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)

  // Doctor Review Form
  const [reviewStatus, setReviewStatus] = useState('REVIEWED')
  const [clinicalNotes, setClinicalNotes] = useState('')
  const [submittingReview, setSubmittingReview] = useState(false)

  // Parameter Correction Modal State
  const [correctingParam, setCorrectingParam] = useState(null)
  const [newCorrectedValue, setNewCorrectedValue] = useState('')
  const [correctionReason, setCorrectionReason] = useState('')
  const [submittingCorrection, setSubmittingCorrection] = useState(false)

  // 1. Fetch Authorized Patients from Doctor Appointments
  const loadAuthorizedPatients = useCallback(async () => {
    try {
      setPatientsLoading(true)
      const appts = await getMyAppointments({ limit: 100 })
      const patientMap = new Map()
      ;(appts || []).forEach((a) => {
        if (a.patient_id && !patientMap.has(a.patient_id)) {
          patientMap.set(a.patient_id, {
            id: a.patient_id,
            name: a.patient?.full_name || `Patient #${a.patient_id.slice(0, 8)}`,
            email: a.patient?.email || '',
            appointment_date: a.appointment_date,
          })
        }
      })
      const list = Array.from(patientMap.values())
      setAuthorizedPatients(list)
      if (list.length > 0 && !selectedPatientId) {
        setSelectedPatientId(list[0].id)
      }
    } catch (err) {
      console.error('Failed to load doctor patients:', err)
      setError('Failed to load authorized patients list.')
    } finally {
      setPatientsLoading(false)
    }
  }, [selectedPatientId])

  useEffect(() => {
    loadAuthorizedPatients()
  }, [loadAuthorizedPatients])

  // 2. Fetch Reports for Selected Patient
  const loadPatientReports = useCallback(async (patientId) => {
    if (!patientId) return
    try {
      setReportsLoading(true)
      setError(null)
      setSelectedDoc(null)
      setDocAnalysis(null)
      const data = await getMedicalReports({ patient_id: patientId })
      setReports(data || [])
    } catch (err) {
      setError(err.message || 'Failed to retrieve patient medical reports.')
      setReports([])
    } finally {
      setReportsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedPatientId) {
      loadPatientReports(selectedPatientId)
    }
  }, [selectedPatientId, loadPatientReports])

  // 3. Inspect Selected Document
  const inspectDocument = async (doc) => {
    setSelectedDoc(doc)
    setAnalysisLoading(true)
    setDocAnalysis(null)
    setDocSummary(null)
    setSuccessMsg(null)
    try {
      const [analysis, summary] = await Promise.all([
        getMedicalReportAnalysis(doc.id),
        getMedicalReportSummary(doc.id).catch(() => null),
      ])
      setDocAnalysis(analysis)
      setDocSummary(summary || analysis?.summary_json)
    } catch (err) {
      setError(err.message || 'Failed to load document analysis details.')
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 4. Submit Doctor Review
  const handleReviewSubmit = async (e) => {
    e.preventDefault()
    if (!selectedDoc) return

    setSubmittingReview(true)
    setSuccessMsg(null)
    try {
      await submitMedicalReportReview(selectedDoc.id, {
        review_status: reviewStatus,
        clinical_notes: clinicalNotes.trim() || undefined,
      })
      setSuccessMsg(`Clinical review submitted successfully for "${selectedDoc.original_filename}".`)
      setClinicalNotes('')
      // Refresh document details
      await inspectDocument(selectedDoc)
    } catch (err) {
      alert(err.message || 'Failed to submit review.')
    } finally {
      setSubmittingReview(false)
    }
  }

  // 5. Open Correction Modal
  const openCorrectionModal = (param) => {
    setCorrectingParam(param)
    setNewCorrectedValue(param.extracted_value)
    setCorrectionReason('')
  }

  const handleCorrectionSubmit = async (e) => {
    e.preventDefault()
    if (!selectedDoc || !correctingParam) return
    if (!correctionReason.trim()) {
      alert('Please provide a clinical justification for correcting this parameter.')
      return
    }

    setSubmittingCorrection(true)
    try {
      await correctMedicalParameter(selectedDoc.id, correctingParam.id, {
        corrected_value: newCorrectedValue.trim(),
        correction_reason: correctionReason.trim(),
      })
      setSuccessMsg(`Parameter "${correctingParam.canonical_name}" corrected and audited.`)
      setCorrectingParam(null)
      // Refresh analysis
      await inspectDocument(selectedDoc)
    } catch (err) {
      alert(err.message || 'Failed to save parameter correction.')
    } finally {
      setSubmittingCorrection(false)
    }
  }

  // Range Status Badges
  const renderRangeStatusBadge = (status, isCrit) => {
    if (isCrit || status === 'CRITICAL_REVIEW_REQUIRED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-ping" />
          Critical Review
        </span>
      )
    }
    switch (status) {
      case 'WITHIN_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            Within Range
          </span>
        )
      case 'BELOW_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            ↓ Low
          </span>
        )
      case 'ABOVE_RANGE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            ↑ High
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
            No Range
          </span>
        )
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-brand-border/60 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
              Clinical Medical Reports Review
            </h1>
            <span className="px-2.5 py-0.5 rounded-md text-[11px] font-bold bg-teal-800 text-white uppercase tracking-wider">
              Doctor Workspace
            </span>
          </div>
          <p className="text-sm text-brand-muted mt-1 max-w-3xl">
            Review patient laboratory reports, verify AI extraction accuracy, correct abnormal values with audited
            rationale, and submit official clinical review determinations.
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
          {successMsg}
        </div>
      )}

      {/* Patient Selection Bar */}
      <div className="bg-brand-surface rounded-2xl border border-brand-border/80 shadow-clinical-sm p-5">
        <label className="block text-xs font-bold text-brand-muted uppercase tracking-wider mb-2">
          Select Patient Under Clinical Care
        </label>
        {patientsLoading ? (
          <div className="h-10 bg-brand-ground rounded-xl animate-pulse" />
        ) : authorizedPatients.length === 0 ? (
          <p className="text-xs text-brand-muted italic">
            No authorized patient appointments found on file. Patients with whom you have scheduled consultations will appear here.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {authorizedPatients.map((p) => {
              const isSelected = p.id === selectedPatientId
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedPatientId(p.id)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'border-brand-accent bg-teal-50/60 ring-2 ring-brand-accent/20'
                      : 'border-brand-border hover:bg-brand-ground/50'
                  }`}
                >
                  <span className="font-bold text-sm text-brand-text block truncate">{p.name}</span>
                  <span className="text-[11px] text-brand-muted block mt-0.5">
                    Appointment: {p.appointment_date || 'Recent'}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Two-Column Clinical Review Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Reports List (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-brand-surface rounded-2xl border border-brand-border/80 shadow-clinical-sm p-5 space-y-3">
            <h2 className="text-sm font-bold text-brand-text">Patient Documents ({reports.length})</h2>
            {reportsLoading ? (
              <div className="space-y-2">
                <SkeletonCard />
                <SkeletonCard />
              </div>
            ) : reports.length === 0 ? (
              <div className="p-6 text-center text-xs text-brand-muted">
                No medical reports uploaded by this patient yet.
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
                {reports.map((doc) => {
                  const isSelected = selectedDoc?.id === doc.id
                  return (
                    <div
                      key={doc.id}
                      onClick={() => inspectDocument(doc)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? 'border-brand-accent bg-teal-50/70 shadow-xs'
                          : 'border-brand-border hover:bg-brand-ground/40'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-bold text-xs text-brand-text truncate block">{doc.original_filename}</span>
                        <span className="text-[10px] text-brand-muted font-medium shrink-0">
                          {doc.report_date || 'N/A'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-teal-100/70 text-teal-800">
                          {doc.document_category}
                        </span>
                        {doc.processing_status === 'COMPLETED' ? (
                          <span className="text-[10px] font-semibold text-emerald-700">✓ Extracted</span>
                        ) : (
                          <span className="text-[10px] font-semibold text-amber-700">Pending</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Document Analysis, Parameter Table & Verification (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {!selectedDoc ? (
            <div className="p-12 text-center bg-brand-surface rounded-2xl border border-brand-border shadow-clinical-sm">
              <ClinicalIcon name="document" size={36} className="mx-auto text-brand-muted mb-2" />
              <h3 className="text-base font-bold text-brand-text">Select a report to review</h3>
              <p className="text-xs text-brand-muted mt-1 max-w-md mx-auto">
                Choose a medical document from the left list to inspect extracted lab parameters, verify ranges, or submit clinical review determinations.
              </p>
            </div>
          ) : analysisLoading ? (
            <div className="p-12 text-center bg-brand-surface rounded-2xl border border-brand-border shadow-clinical-sm">
              <div className="w-8 h-8 border-2 border-brand-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <span className="text-xs text-brand-muted">Loading laboratory analysis...</span>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Document Overview Header */}
              <div className="bg-brand-surface rounded-2xl border border-brand-border shadow-clinical-sm p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-brand-border/60 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-brand-text">{selectedDoc.original_filename}</h2>
                    <span className="text-xs text-brand-muted">
                      Category: <strong className="text-teal-800">{selectedDoc.document_category}</strong> • Date:{' '}
                      {selectedDoc.report_date || 'Unrecorded'} • SHA-256: {selectedDoc.sha256_hash.slice(0, 12)}...
                    </span>
                  </div>
                  <a
                    href={`/api/v1/medical-reports/${selectedDoc.id}/download`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-brand-ground hover:bg-brand-mint text-brand-text border border-brand-border"
                  >
                    <ClinicalIcon name="download" size={14} /> View Original PDF
                  </a>
                </div>

                {/* AI Executive Summary Card */}
                {docSummary && (
                  <div className="p-4 rounded-xl bg-teal-50/50 border border-teal-200/70 space-y-2 text-xs">
                    <span className="font-bold text-teal-900 uppercase tracking-wider block">
                      AI Extraction Summary
                    </span>
                    <p className="text-teal-950 font-medium leading-relaxed">{docSummary.report_overview}</p>
                    {docSummary.important_observations?.length > 0 && (
                      <ul className="list-disc list-inside space-y-0.5 text-teal-900 pt-1">
                        {docSummary.important_observations.map((obs, i) => (
                          <li key={i}>{obs}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>

              {/* Extracted Parameters Table with Physician Correction Controls */}
              <div className="bg-brand-surface rounded-2xl border border-brand-border shadow-clinical-sm p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-brand-text">
                    Extracted Laboratory Parameters ({docAnalysis?.parameters?.length || 0})
                  </h3>
                  <span className="text-xs text-brand-muted">
                    Click &quot;Correct&quot; to edit values with audit tracking
                  </span>
                </div>

                <div className="rounded-xl border border-brand-border overflow-hidden">
                  <table className="min-w-full divide-y divide-brand-border text-left text-xs">
                    <thead className="bg-brand-ground/60 text-brand-muted font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Parameter Name</th>
                        <th className="py-2.5 px-3">Extracted Value</th>
                        <th className="py-2.5 px-3">Unit</th>
                        <th className="py-2.5 px-3">Reference Range</th>
                        <th className="py-2.5 px-3">Range Status</th>
                        <th className="py-2.5 px-3">Verification</th>
                        <th className="py-2.5 px-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-brand-border/40 text-brand-text">
                      {(docAnalysis?.parameters || []).map((p) => (
                        <tr key={p.id} className="hover:bg-brand-ground/30">
                          <td className="py-2.5 px-3 font-semibold text-brand-text">
                            {p.canonical_name}
                            <span className="block text-[10px] text-brand-muted font-normal">
                              Raw: {p.parameter_name} (p. {p.source_page})
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-sm">
                            {p.extracted_value}
                          </td>
                          <td className="py-2.5 px-3 text-brand-muted">{p.original_unit || '—'}</td>
                          <td className="py-2.5 px-3 font-mono text-brand-muted">
                            {p.reference_range_text || 'None reported'}
                          </td>
                          <td className="py-2.5 px-3">
                            {renderRangeStatusBadge(p.range_status, p.is_critical)}
                          </td>
                          <td className="py-2.5 px-3">
                            {p.verification_status === 'DOCTOR_VERIFIED' ? (
                              <span className="text-[10px] font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                                Verified
                              </span>
                            ) : p.verification_status === 'DOCTOR_CORRECTED' ? (
                              <span className="text-[10px] font-bold text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                                Corrected
                              </span>
                            ) : (
                              <span className="text-[10px] text-slate-400">Unverified</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => openCorrectionModal(p)}
                              className="text-xs font-semibold text-brand-accent hover:underline px-2 py-1"
                            >
                              Correct
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Physician Review & Clinical Determination Card */}
              <div className="bg-brand-surface rounded-2xl border border-brand-border shadow-clinical-sm p-6 space-y-4">
                <h3 className="text-sm font-bold text-brand-text">Physician Clinical Determination</h3>
                <form onSubmit={handleReviewSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                        Review Status
                      </label>
                      <select
                        value={reviewStatus}
                        onChange={(e) => setReviewStatus(e.target.value)}
                        className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent font-semibold"
                      >
                        <option value="REVIEWED">REVIEWED (Extraction Confirmed)</option>
                        <option value="CORRECTIONS_MADE">CORRECTIONS_MADE (Values Modified)</option>
                        <option value="REPEAT_TEST_RECOMMENDED">REPEAT_TEST_RECOMMENDED (Specimen Retest)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                      Physician Clinical Notes & Recommendations
                    </label>
                    <textarea
                      rows={3}
                      value={clinicalNotes}
                      onChange={(e) => setClinicalNotes(e.target.value)}
                      placeholder="Add clinical context, follow-up recommendations, or patient advice..."
                      className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent"
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="submit"
                      variant="primary"
                      disabled={submittingReview}
                      loading={submittingReview}
                      className="px-6"
                    >
                      Submit Official Clinical Review
                    </Button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Parameter Correction Modal */}
      {correctingParam && (
        <Modal isOpen={!!correctingParam} onClose={() => setCorrectingParam(null)} size="md">
          <ModalHeader onClose={() => setCorrectingParam(null)}>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-800">
                <ClinicalIcon name="activity" size={18} />
              </span>
              <div>
                <h3 className="text-base font-bold text-brand-text">
                  Correct Parameter: {correctingParam.canonical_name}
                </h3>
                <span className="text-xs text-brand-muted">
                  Originally Extracted: {correctingParam.extracted_value} {correctingParam.original_unit}
                </span>
              </div>
            </div>
          </ModalHeader>
          <ModalBody>
            <form onSubmit={handleCorrectionSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                  Corrected Measurement Value
                </label>
                <input
                  type="text"
                  required
                  value={newCorrectedValue}
                  onChange={(e) => setNewCorrectedValue(e.target.value)}
                  placeholder="e.g., 14.5"
                  className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent font-mono font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-brand-muted uppercase tracking-wider mb-1">
                  Clinical Rationale for Correction (Audited)
                </label>
                <textarea
                  rows={3}
                  required
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  placeholder="e.g., Decimal misaligned in OCR; laboratory report confirms 14.5 g/dL."
                  className="w-full px-3 py-2 text-sm rounded-xl border border-brand-border bg-white text-brand-text focus:ring-2 focus:ring-brand-accent"
                />
                <span className="text-[11px] text-brand-muted mt-1 block">
                  This correction and clinical rationale will be immutably recorded in the clinical audit log.
                </span>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCorrectingParam(null)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={submittingCorrection}
                  loading={submittingCorrection}
                >
                  Save Audited Correction
                </Button>
              </div>
            </form>
          </ModalBody>
        </Modal>
      )}
    </div>
  )
}
