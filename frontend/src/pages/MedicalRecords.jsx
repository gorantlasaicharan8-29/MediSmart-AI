import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getMyMedicalHistory } from '../services/api'
import {
  Badge,
  Button,
  ClinicalIcon,
  EmptyState,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Skeleton,
} from '../components/ui'

export default function MedicalRecords() {
  const [medicalHistory, setMedicalHistory] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('consultations') // 'consultations', 'prescriptions', 'diagnoses', 'followups'
  const [selectedConsultation, setSelectedConsultation] = useState(null)

  const fetchRecords = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getMyMedicalHistory()
      setMedicalHistory(data)
    } catch (err) {
      setError(err.message || 'Unable to load your medical records. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  const consultations = medicalHistory?.consultations || []
  const diagnoses = medicalHistory?.diagnoses || []
  const prescriptions = medicalHistory?.prescriptions || []
  const followUps = medicalHistory?.upcoming_follow_ups || medicalHistory?.follow_ups || []

  const formatDate = (isoString) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    } catch {
      return isoString
    }
  }

  const formatDateTime = (isoString) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-teal-50 text-teal-800 border border-teal-200">
              <ClinicalIcon name="shield-check" size={13} className="text-teal-600" />
              Verified Electronic Health Record (EHR)
            </span>
            <span className="text-xs text-brand-muted hidden sm:inline">&bull;</span>
            <span className="text-xs text-brand-muted hidden sm:inline">HIPAA & GDPR Standards</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            My Medical Records
          </h1>
          <p className="text-sm text-brand-muted mt-1 max-w-2xl">
            Review your complete clinical consultation timeline, clinician diagnoses, official digital prescriptions, and recommended follow-up care plans.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRecords}
            disabled={isLoading}
            className="text-xs cursor-pointer"
          >
            <ClinicalIcon
              name="refresh"
              size={14}
              className={`mr-1.5 ${isLoading ? 'animate-spin' : ''}`}
            />
            Sync Records
          </Button>
          <Button
            as={Link}
            to="/appointments"
            variant="primary"
            size="sm"
            className="text-xs cursor-pointer font-bold"
          >
            <ClinicalIcon name="calendar" size={14} className="mr-1.5" />
            Book Consultation
          </Button>
        </div>
      </div>

      {/* Security & Access Banner */}
      <div className="rounded-2xl bg-teal-50/70 border border-teal-200/80 p-4 text-xs text-teal-900 flex items-start gap-3">
        <ClinicalIcon name="shield-check" size={20} className="text-teal-600 shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-bold">Strict Patient Confidentiality & RBAC Protection</p>
          <p className="text-teal-800/90 leading-relaxed">
            Your medical history is cryptographically scoped to your authenticated identity. Only your assigned treating clinicians and hospital administrators have authorization to view or contribute to your clinical chart.
          </p>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-1">
          <div className="flex items-center justify-between text-brand-muted">
            <span className="text-xs font-semibold">Consultations</span>
            <div className="w-7 h-7 rounded-lg bg-teal-50 text-brand-primary flex items-center justify-center">
              <ClinicalIcon name="stethoscope" size={15} />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-brand-text">
            {isLoading ? <Skeleton className="h-8 w-12 rounded" /> : consultations.length}
          </div>
          <p className="text-[11px] text-brand-muted">Recorded encounters</p>
        </div>

        <div className="p-4 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-1">
          <div className="flex items-center justify-between text-brand-muted">
            <span className="text-xs font-semibold">Diagnoses</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <ClinicalIcon name="activity" size={15} />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-brand-text">
            {isLoading ? <Skeleton className="h-8 w-12 rounded" /> : diagnoses.length}
          </div>
          <p className="text-[11px] text-brand-muted">Clinician findings</p>
        </div>

        <div className="p-4 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-1">
          <div className="flex items-center justify-between text-brand-muted">
            <span className="text-xs font-semibold">Prescriptions</span>
            <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center">
              <ClinicalIcon name="pill" size={15} />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-brand-text">
            {isLoading ? <Skeleton className="h-8 w-12 rounded" /> : prescriptions.length}
          </div>
          <p className="text-[11px] text-brand-muted">Digital Rx issued</p>
        </div>

        <div className="p-4 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-1">
          <div className="flex items-center justify-between text-brand-muted">
            <span className="text-xs font-semibold">Follow-Up Plans</span>
            <div className="w-7 h-7 rounded-lg bg-amber-50 text-amber-700 flex items-center justify-center">
              <ClinicalIcon name="clock" size={15} />
            </div>
          </div>
          <div className="text-2xl font-extrabold text-brand-text">
            {isLoading ? <Skeleton className="h-8 w-12 rounded" /> : followUps.length}
          </div>
          <p className="text-[11px] text-brand-muted">Care instructions</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-brand-border/70 overflow-x-auto pb-1">
        <button
          type="button"
          onClick={() => setActiveTab('consultations')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'consultations'
              ? 'bg-brand-mint/80 text-brand-deep shadow-xs'
              : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
          }`}
        >
          <ClinicalIcon name="notes" size={15} />
          Consultation Timeline ({consultations.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('prescriptions')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'prescriptions'
              ? 'bg-brand-mint/80 text-brand-deep shadow-xs'
              : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
          }`}
        >
          <ClinicalIcon name="pill" size={15} />
          Digital Prescriptions ({prescriptions.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('diagnoses')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'diagnoses'
              ? 'bg-brand-mint/80 text-brand-deep shadow-xs'
              : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
          }`}
        >
          <ClinicalIcon name="activity" size={15} />
          Diagnoses ({diagnoses.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('followups')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap cursor-pointer ${
            activeTab === 'followups'
              ? 'bg-brand-mint/80 text-brand-deep shadow-xs'
              : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
          }`}
        >
          <ClinicalIcon name="calendar" size={15} />
          Follow-Up Care ({followUps.length})
        </button>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-4 py-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="p-6 rounded-3xl bg-brand-surface border border-brand-border space-y-4 animate-pulse"
            >
              <div className="flex justify-between items-center">
                <Skeleton className="h-5 w-1/3 rounded-lg" />
                <Skeleton className="h-5 w-24 rounded-full" />
              </div>
              <Skeleton className="h-4 w-2/3 rounded-md" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          ))}
        </div>
      )}

      {/* Error Banner */}
      {!isLoading && error && (
        <div className="p-5 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <ClinicalIcon name="alert-circle" size={20} className="shrink-0" />
            <span>{error}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={fetchRecords}
            className="shrink-0 border-clinical-danger/30 hover:bg-clinical-danger/10 text-clinical-danger"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Tab 1: Consultation Timeline */}
      {!isLoading && !error && activeTab === 'consultations' && (
        <div className="space-y-6">
          {consultations.length === 0 ? (
            <EmptyState
              icon="notes"
              title="No Consultations Recorded"
              description="You do not have any clinical consultation records in your Electronic Health Record yet. Completed appointments with doctor documentation will appear here."
              className="py-12 bg-brand-surface border border-brand-border rounded-3xl"
            />
          ) : (
            <div className="relative border-l-2 border-teal-200/80 ml-4 sm:ml-6 pl-6 sm:pl-8 space-y-8">
              {consultations.map((note) => {
                const docName = note.doctor_name || note.doctor?.full_name || 'Dr. Healthcare Specialist'
                const docSpecialty = note.doctor_specialty || note.doctor?.specialty || 'General Medicine'
                const hospName = note.hospital_name || note.doctor?.hospital_name || 'MediSmart Medical Center'
                const consultTime = formatDateTime(note.consultation_date)

                return (
                  <div key={note.id} className="relative group">
                    {/* Timeline Node Dot */}
                    <div className="absolute -left-[31px] sm:-left-[39px] top-1.5 w-4 h-4 rounded-full bg-teal-500 border-4 border-brand-ground shadow-xs group-hover:scale-125 transition-transform" />

                    {/* Encounter Card */}
                    <div className="p-5 sm:p-6 rounded-3xl bg-brand-surface border border-brand-border shadow-clinical-xs hover:border-teal-300/80 transition-all space-y-4">
                      {/* Card Header */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-brand-border/60">
                        <div>
                          <span className="text-[10px] uppercase font-bold text-teal-700 tracking-wider">
                            Consultation Encounter
                          </span>
                          <h3 className="text-base font-bold text-brand-text">
                            {docName} &bull; <span className="text-brand-muted font-normal">{docSpecialty}</span>
                          </h3>
                          <p className="text-xs text-brand-muted">
                            {hospName} &bull; Ref: <span className="font-mono">{note.appointment_id.slice(0, 8)}</span>
                          </p>
                        </div>
                        <div className="flex sm:flex-col sm:items-end justify-between items-center">
                          <span className="text-xs font-bold text-brand-text">{consultTime}</span>
                          <Badge variant="teal" size="sm" className="mt-0.5">
                            Signed Clinical Record
                          </Badge>
                        </div>
                      </div>

                      {/* Chief Complaint & Symptoms */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border">
                          <span className="text-[10px] uppercase font-bold text-brand-muted block mb-1">
                            Chief Complaint
                          </span>
                          <p className="text-brand-text font-medium">{note.chief_complaint || 'None specified'}</p>
                        </div>

                        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border">
                          <span className="text-[10px] uppercase font-bold text-brand-muted block mb-1">
                            Reported Symptoms
                          </span>
                          <p className="text-brand-text">{note.symptoms || 'None reported'}</p>
                        </div>
                      </div>

                      {/* Clinical Observations & Examination */}
                      {note.clinical_observations && (
                        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border text-xs">
                          <span className="text-[10px] uppercase font-bold text-brand-muted block mb-1">
                            Clinical Observations & Examination
                          </span>
                          <p className="text-brand-text leading-relaxed">{note.clinical_observations}</p>
                        </div>
                      )}

                      {/* Diagnosis Summary */}
                      <div className="p-3.5 rounded-2xl bg-teal-50/60 border border-teal-200/70 text-xs space-y-1">
                        <div className="flex items-center gap-2">
                          <ClinicalIcon name="activity" size={14} className="text-teal-700" />
                          <span className="text-[10px] uppercase font-bold text-teal-800 tracking-wider">
                            Clinician Diagnosis Summary
                          </span>
                        </div>
                        <p className="text-brand-text font-bold leading-relaxed">{note.diagnosis_summary}</p>
                      </div>

                      {/* Treatment Plan & Recommendations */}
                      <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border text-xs space-y-1">
                        <span className="text-[10px] uppercase font-bold text-brand-muted block">
                          Treatment Plan & Doctor Recommendations
                        </span>
                        <p className="text-brand-text leading-relaxed">
                          {note.treatment_plan || 'Treatment instructions discussed during clinical consultation.'}
                        </p>
                        {note.doctor_recommendations && (
                          <p className="text-brand-muted italic mt-1 pt-1 border-t border-brand-border/60">
                            Recommendations: {note.doctor_recommendations}
                          </p>
                        )}
                      </div>

                      {/* Attached Items Badges & Actions */}
                      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          {note.prescriptions?.length > 0 && (
                            <button
                              type="button"
                              onClick={() => setActiveTab('prescriptions')}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors cursor-pointer"
                            >
                              <ClinicalIcon name="pill" size={12} />
                              {note.prescriptions[0].prescription_number} ({note.prescriptions[0].items?.length || 0} meds)
                            </button>
                          )}

                          {note.diagnoses?.length > 0 && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                              <ClinicalIcon name="activity" size={12} />
                              {note.diagnoses.length} Diagnoses Linked
                            </span>
                          )}

                          {note.follow_up_recommended_date && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                              <ClinicalIcon name="calendar" size={12} />
                              Follow-Up: {formatDate(note.follow_up_recommended_date)}
                            </span>
                          )}
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedConsultation(note)}
                          className="text-xs font-bold text-brand-primary hover:text-brand-deep cursor-pointer"
                        >
                          <ClinicalIcon name="eye" size={13} className="mr-1" />
                          View Full Record
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Digital Prescriptions */}
      {!isLoading && !error && activeTab === 'prescriptions' && (
        <div className="space-y-6">
          {prescriptions.length === 0 ? (
            <EmptyState
              icon="pill"
              title="No Prescriptions Issued"
              description="You do not have any official digital prescriptions on file. When an authorized doctor prescribes medication during your consultation, the Rx instructions will appear here."
              className="py-12 bg-brand-surface border border-brand-border rounded-3xl"
            />
          ) : (
            <div className="grid grid-cols-1 gap-6">
              {prescriptions.map((rx) => {
                const docName = rx.doctor_name || rx.doctor?.full_name || 'Prescribing Clinician'
                const docSpecialty = rx.doctor_specialty || rx.doctor?.specialty || 'Medical Specialist'
                const hospName = rx.hospital_name || rx.doctor?.hospital_name || 'Hospital Clinic'
                const rxDate = formatDate(rx.prescription_date)

                return (
                  <div
                    key={rx.id}
                    className="p-6 rounded-3xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-4 hover:border-indigo-200 transition-all"
                  >
                    {/* Prescription Banner Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-border/70">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold">
                          <ClinicalIcon name="pill" size={20} />
                        </div>
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-base font-extrabold text-brand-text font-mono">
                              {rx.prescription_number}
                            </h3>
                            <Badge variant={rx.is_active ? 'info' : 'neutral'} size="sm">
                              {rx.is_active ? `Revision v${rx.version || 1}` : `Superseded (v${rx.version || 1})`}
                            </Badge>
                            {!rx.is_active && (
                              <Badge variant="warning" size="sm">
                                Amended
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-brand-muted">
                            Issued by {docName} ({docSpecialty}) &bull; {hospName}
                          </p>
                        </div>
                      </div>

                      <div className="text-left sm:text-right">
                        <span className="text-[10px] uppercase font-bold text-brand-muted block">
                          Prescription Date
                        </span>
                        <span className="text-xs font-bold text-brand-text">{rxDate}</span>
                      </div>
                    </div>

                    {/* Prescription Medications Table */}
                    <div className="overflow-x-auto rounded-2xl border border-brand-border">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="bg-brand-ground/80 border-b border-brand-border text-brand-muted uppercase tracking-wider font-bold text-[10px]">
                            <th className="py-2.5 px-4">Medication Name</th>
                            <th className="py-2.5 px-4">Dosage</th>
                            <th className="py-2.5 px-4">Frequency</th>
                            <th className="py-2.5 px-4">Duration</th>
                            <th className="py-2.5 px-4">Route</th>
                            <th className="py-2.5 px-4">Instructions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-brand-border/60">
                          {rx.items?.map((item, idx) => (
                            <tr key={item.id || idx} className="hover:bg-brand-ground/30">
                              <td className="py-3 px-4 font-bold text-brand-text">{item.medication_name}</td>
                              <td className="py-3 px-4 text-brand-muted">{item.dosage}</td>
                              <td className="py-3 px-4 font-medium text-brand-text">{item.frequency}</td>
                              <td className="py-3 px-4 text-brand-muted">{item.duration}</td>
                              <td className="py-3 px-4 text-brand-muted uppercase text-[10px] font-bold">
                                {item.route || 'Oral'}
                              </td>
                              <td className="py-3 px-4 text-brand-text leading-relaxed">
                                {item.instructions || 'As advised'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Amendment Rationale if present */}
                    {rx.amendment_reason && (
                      <div className="p-3 rounded-2xl bg-amber-50/70 border border-amber-200/80 text-xs space-y-1">
                        <span className="text-[10px] uppercase font-bold text-amber-900 block">
                          Clinical Amendment Rationale
                        </span>
                        <p className="text-amber-950 font-medium leading-relaxed">{rx.amendment_reason}</p>
                      </div>
                    )}

                    {/* Clinical / Dispense Notes */}
                    {rx.notes && (
                      <div className="p-3 rounded-2xl bg-indigo-50/50 border border-indigo-100 text-xs space-y-1">
                        <span className="text-[10px] uppercase font-bold text-indigo-900 block">
                          Doctor Dispensing Notes & Patient Advice
                        </span>
                        <p className="text-brand-text leading-relaxed">{rx.notes}</p>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Clinician Diagnoses */}
      {!isLoading && !error && activeTab === 'diagnoses' && (
        <div className="space-y-6">
          {diagnoses.length === 0 ? (
            <EmptyState
              icon="activity"
              title="No Diagnoses Recorded"
              description="No clinical diagnoses have been entered into your medical record. Diagnoses submitted by your physician during consultation will be compiled here."
              className="py-12 bg-brand-surface border border-brand-border rounded-3xl"
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {diagnoses.map((diag) => {
                const docName = diag.doctor_name || diag.doctor?.full_name || 'Clinician'
                const docSpecialty = diag.doctor_specialty || diag.doctor?.specialty || 'Physician'
                const diagDate = formatDate(diag.diagnosis_date)

                return (
                  <div
                    key={diag.id}
                    className="p-5 rounded-3xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3 className="text-base font-bold text-brand-text">{diag.diagnosis_name}</h3>
                        <p className="text-xs text-brand-muted">
                          Diagnosed by {docName} &bull; {docSpecialty}
                        </p>
                      </div>
                      {diag.diagnosis_code ? (
                        <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono font-bold text-xs">
                          {diag.diagnosis_code}
                        </span>
                      ) : (
                        <Badge variant="neutral" size="sm">
                          Clinical Finding
                        </Badge>
                      )}
                    </div>

                    {diag.description && (
                      <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border text-xs text-brand-text">
                        {diag.description}
                      </div>
                    )}

                    <div className="flex items-center justify-between text-[11px] text-brand-muted pt-1 border-t border-brand-border/60">
                      <span>Date: {diagDate}</span>
                      <span className="font-mono">ID: {diag.id.slice(0, 8)}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Follow-Up Care */}
      {!isLoading && !error && activeTab === 'followups' && (
        <div className="space-y-6">
          {followUps.length === 0 ? (
            <EmptyState
              icon="calendar"
              title="No Pending Follow-Ups"
              description="You do not have any recommended follow-up appointments at this time. When a clinician prescribes a check-up date or follow-up instructions, you can view and book them here."
              className="py-12 bg-brand-surface border border-brand-border rounded-3xl"
            />
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {followUps.map((fu) => {
                const docName = fu.doctor_name || fu.doctor?.full_name || 'Doctor'
                const docSpecialty = fu.doctor_specialty || fu.doctor?.specialty || 'Specialist'
                const hospName = fu.hospital_name || fu.doctor?.hospital_name || 'Medical Center'
                const recDate = formatDate(fu.recommended_date)

                return (
                  <div
                    key={fu.id}
                    className="p-6 rounded-3xl bg-brand-surface border border-brand-border shadow-clinical-xs space-y-4 hover:border-amber-200 transition-all"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-brand-border/70">
                      <div>
                        <span className="text-[10px] uppercase font-bold text-amber-700 tracking-wider">
                          Doctor Recommended Follow-Up
                        </span>
                        <h3 className="text-base font-bold text-brand-text">
                          Target Consultation Date: {recDate}
                        </h3>
                        <p className="text-xs text-brand-muted">
                          Recommended by {docName} ({docSpecialty}) &bull; {hospName}
                        </p>
                      </div>

                      <Badge variant="warning" size="sm">
                        Follow-Up Recommended
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                      {fu.reason && (
                        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border">
                          <span className="text-[10px] uppercase font-bold text-brand-muted block mb-1">
                            Reason for Follow-Up
                          </span>
                          <p className="text-brand-text">{fu.reason}</p>
                        </div>
                      )}

                      {fu.instructions && (
                        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border">
                          <span className="text-[10px] uppercase font-bold text-brand-muted block mb-1">
                            Patient Instructions Before Visit
                          </span>
                          <p className="text-brand-text">{fu.instructions}</p>
                        </div>
                      )}
                    </div>

                    <div className="pt-2 flex justify-end">
                      <Button
                        as={Link}
                        to="/appointments"
                        variant="primary"
                        size="sm"
                        className="text-xs font-bold cursor-pointer"
                      >
                        <ClinicalIcon name="calendar" size={13} className="mr-1.5" />
                        Book Recommended Appointment
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Detailed Full Consultation Encounter Modal */}
      {selectedConsultation && (
        <Modal
          isOpen={Boolean(selectedConsultation)}
          onClose={() => setSelectedConsultation(null)}
          title="Clinical Consultation Summary"
          size="lg"
        >
          <ModalHeader onClose={() => setSelectedConsultation(null)}>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-brand-text">
                Encounter Chart &bull; {formatDateTime(selectedConsultation.consultation_date)}
              </span>
              <Badge variant="teal" size="sm">
                Signed EHR
              </Badge>
            </div>
          </ModalHeader>

          <ModalBody className="space-y-4">
            <div className="p-4 rounded-2xl bg-brand-ground border border-brand-border space-y-1 text-xs">
              <span className="text-[10px] uppercase font-bold text-brand-muted block">
                Treating Clinician & Healthcare Facility
              </span>
              <p className="font-bold text-brand-text">
                {selectedConsultation.doctor_name || selectedConsultation.doctor?.full_name || 'Doctor'} &bull;{' '}
                <span className="font-normal text-brand-muted">
                  {selectedConsultation.doctor_specialty || selectedConsultation.doctor?.specialty}
                </span>
              </p>
              <p className="text-brand-muted">
                Facility: {selectedConsultation.hospital_name || selectedConsultation.doctor?.hospital_name || 'Hospital Center'}
              </p>
            </div>

            <div className="space-y-2 text-xs">
              <span className="text-[10px] uppercase font-bold text-brand-muted block">
                Chief Complaint & Clinical Symptoms
              </span>
              <div className="p-3 rounded-2xl bg-brand-surface border border-brand-border space-y-1">
                <p className="font-semibold text-brand-text">
                  Complaint: {selectedConsultation.chief_complaint || 'N/A'}
                </p>
                <p className="text-brand-muted">
                  Symptoms: {selectedConsultation.symptoms || 'N/A'}
                </p>
              </div>
            </div>

            {selectedConsultation.clinical_observations && (
              <div className="space-y-2 text-xs">
                <span className="text-[10px] uppercase font-bold text-brand-muted block">
                  Clinical Observations & Physical Examination
                </span>
                <div className="p-3 rounded-2xl bg-brand-surface border border-brand-border leading-relaxed text-brand-text">
                  {selectedConsultation.clinical_observations}
                </div>
              </div>
            )}

            <div className="space-y-2 text-xs">
              <span className="text-[10px] uppercase font-bold text-brand-muted block">
                Diagnosis Summary
              </span>
              <div className="p-3 rounded-2xl bg-teal-50 border border-teal-200 text-teal-950 font-semibold leading-relaxed">
                {selectedConsultation.diagnosis_summary}
              </div>
            </div>

            <div className="space-y-2 text-xs">
              <span className="text-[10px] uppercase font-bold text-brand-muted block">
                Treatment Plan & Clinical Directives
              </span>
              <div className="p-3 rounded-2xl bg-brand-surface border border-brand-border space-y-2">
                <p className="text-brand-text leading-relaxed">
                  {selectedConsultation.treatment_plan || 'As advised.'}
                </p>
                {selectedConsultation.doctor_recommendations && (
                  <p className="text-brand-muted italic pt-1 border-t border-brand-border/60">
                    Recommendations: {selectedConsultation.doctor_recommendations}
                  </p>
                )}
              </div>
            </div>
          </ModalBody>

          <ModalFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedConsultation(null)}
              className="text-xs cursor-pointer"
            >
              Close
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </div>
  )
}
