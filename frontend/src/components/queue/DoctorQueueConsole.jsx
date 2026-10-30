import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import {
  getDoctorClinicalQueue,
  callQueuePatient,
  completeQueuePatient,
  skipQueuePatient,
  recallQueuePatient,
  getDoctors,
} from '../../services/api'
import { useQueueSocket } from '../../hooks/useQueueSocket'
import { playChime } from '../../utils/sound'
import {
  Button,
  Badge,
  Skeleton,
  EmptyState,
  ClinicalIcon,
} from '../ui'

export default function DoctorQueueConsole({ initialDoctorId = null }) {
  const { doctorId: routeDoctorId } = useParams()
  const { user, isAuthenticated } = useAuth()

  // Active doctor ID resolution
  const [activeDoctorId, setActiveDoctorId] = useState(initialDoctorId || routeDoctorId || '')
  const [doctorsList, setDoctorsList] = useState([])
  const [isLoadingDoctors, setIsLoadingDoctors] = useState(false)
  const [doctorProfileNotFound, setDoctorProfileNotFound] = useState(false)

  // Clinical queue data
  const [queueData, setQueueData] = useState(null)
  const [isLoadingQueue, setIsLoadingQueue] = useState(true)
  const [queueError, setQueueError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [isSubmittingAction, setIsSubmittingAction] = useState(false)

  // Track recently skipped entries in current session for direct 1-click recall
  const [skippedHistory, setSkippedHistory] = useState([])

  // Clinical notes state for the active consultation
  const [consultationNotes, setConsultationNotes] = useState('')

  // Active consultation elapsed timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  // Tab for queue view: 'waiting' vs 'skipped'
  const [activeTab, setActiveTab] = useState('waiting')

  // Resolve Doctor ID for authenticated doctor or staff
  useEffect(() => {
    let isMounted = true
    const resolveDoctor = async () => {
      if (!isAuthenticated || !user) return

      setIsLoadingDoctors(true)
      try {
        const res = await getDoctors({ page_size: 100 })
        if (!isMounted) return
        const docs = res.items || res || []
        setDoctorsList(docs)

        if (user.role === 'doctor') {
          // Doctors can only manage their own queue
          const myDoc = docs.find((d) => d.user_id === user.id)
          if (myDoc) {
            setActiveDoctorId(myDoc.id)
            setDoctorProfileNotFound(false)
          } else {
            setDoctorProfileNotFound(true)
          }
        } else if (['hospital_admin', 'system_admin'].includes(user.role)) {
          // Admins can select any authorized doctor
          if (!activeDoctorId && docs.length > 0) {
            setActiveDoctorId(docs[0].id)
          }
        }
      } catch (err) {
        if (isMounted) {
          setQueueError(err.message || 'Unable to load doctor roster')
        }
      } finally {
        if (isMounted) setIsLoadingDoctors(false)
      }
    }

    resolveDoctor()
    return () => {
      isMounted = false
    }
  }, [isAuthenticated, user, activeDoctorId])

  // Fetch full clinical queue for active doctor
  const fetchClinicalQueue = useCallback(async () => {
    if (!activeDoctorId) {
      setQueueData(null)
      setIsLoadingQueue(false)
      return null
    }

    try {
      const data = await getDoctorClinicalQueue(activeDoctorId)
      setQueueData(data)
      setQueueError(null)

      // Initialize notes if active consultation has existing notes
      if (data?.current_consultation?.notes) {
        setConsultationNotes(data.current_consultation.notes)
      }

      return data
    } catch (err) {
      const msg = err.message || 'Failed to load clinical queue'
      setQueueError(msg)
      throw err
    } finally {
      setIsLoadingQueue(false)
    }
  }, [activeDoctorId])

  // Real-time WebSocket hook with 10s automatic polling fallback
  const { isLive, connectionMode, lastRefreshed, refresh } = useQueueSocket({
    doctorId: activeDoctorId || null,
    fetcher: fetchClinicalQueue,
    enabled: Boolean(activeDoctorId),
    pollingInterval: 10000,
    onEvent: (event) => {
      // Play alert chime when a new patient checks in
      if (event.action === 'CHECKED_IN') {
        playChime('turn')
      }
    },
  })

  // Timer for active consultation (elapsed seconds since called_at)
  const currentConsultation = queueData?.current_consultation
  const calledAtTimestamp = currentConsultation?.called_at

  useEffect(() => {
    if (!calledAtTimestamp) {
      return
    }

    const timer = setInterval(() => {
      const calledAtTime = new Date(calledAtTimestamp).getTime()
      const nowTime = Date.now()
      const diff = Math.max(0, Math.floor((nowTime - calledAtTime) / 1000))
      setElapsedSeconds(diff)
    }, 1000)

    return () => clearInterval(timer)
  }, [calledAtTimestamp])

  // Format seconds as MM:SS or HH:MM:SS
  const formatTimer = (totalSeconds) => {
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    }
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }

  // Helper to show temporary success feedback
  const showSuccessFeedback = (msg) => {
    setActionSuccess(msg)
    setActionError(null)
    setTimeout(() => setActionSuccess(null), 4000)
  }

  // Action: Call Next Patient (calls top waiting patient)
  const handleCallNext = async () => {
    const nextPatient = queueData?.waiting_list?.[0]
    if (!nextPatient) return
    await handleCallSpecificPatient(nextPatient.id)
  }

  // Action: Call Specific Patient
  const handleCallSpecificPatient = async (entryId) => {
    setIsSubmittingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await callQueuePatient(entryId)
      showSuccessFeedback('Patient called into consultation.')
      setConsultationNotes('')
      await refresh()
    } catch (err) {
      if (err.status === 409) {
        setActionError(
          'Active Consultation Conflict: Another patient is currently in consultation. Please complete or skip the active consultation before calling another patient.'
        )
      } else {
        setActionError(err.message || 'Failed to call patient')
      }
      await refresh()
    } finally {
      setIsSubmittingAction(false)
    }
  }

  // Action: Complete Active Consultation
  const handleCompleteConsultation = async () => {
    if (!currentConsultation) return

    setIsSubmittingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await completeQueuePatient(currentConsultation.id, consultationNotes.trim())
      showSuccessFeedback(`Consultation with Token ${currentConsultation.token_display} completed.`)
      setConsultationNotes('')
      await refresh()
    } catch (err) {
      setActionError(err.message || 'Failed to complete consultation')
      await refresh()
    } finally {
      setIsSubmittingAction(false)
    }
  }

  // Action: Skip Patient (waiting or in-consultation)
  const handleSkipPatient = async (patientItem) => {
    if (!patientItem) return
    const entryId = patientItem.id

    setIsSubmittingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      const isCurrent = currentConsultation && currentConsultation.id === entryId
      const notes = isCurrent ? consultationNotes.trim() : null
      await skipQueuePatient(entryId, notes)
      showSuccessFeedback(`Patient Token ${patientItem.token_display} marked as skipped.`)

      // Add to session skipped history for 1-click recall
      setSkippedHistory((prev) => [
        {
          id: entryId,
          token_display: patientItem.token_display,
          patient_name: patientItem.patient_name,
          appointment_time: patientItem.appointment_time,
          skipped_at: new Date(),
        },
        ...prev.filter((p) => p.id !== entryId),
      ])

      if (isCurrent) setConsultationNotes('')
      await refresh()
    } catch (err) {
      setActionError(err.message || 'Failed to skip patient')
      await refresh()
    } finally {
      setIsSubmittingAction(false)
    }
  }

  // Action: Recall Skipped Patient back to waiting queue
  const handleRecallPatient = async (entryId) => {
    setIsSubmittingAction(true)
    setActionError(null)
    setActionSuccess(null)
    try {
      await recallQueuePatient(entryId)
      showSuccessFeedback('Skipped patient recalled back into waiting queue.')
      setSkippedHistory((prev) => prev.filter((p) => p.id !== entryId))
      await refresh()
    } catch (err) {
      setActionError(err.message || 'Failed to recall patient')
      await refresh()
    } finally {
      setIsSubmittingAction(false)
    }
  }

  // Role Protection Check: Must be clinical staff
  if (!isAuthenticated || !user || !['doctor', 'hospital_admin', 'system_admin'].includes(user.role)) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-8 sm:p-12 text-center space-y-4 shadow-clinical-xs">
        <div className="w-16 h-16 rounded-2xl bg-clinical-warning-bg text-clinical-warning flex items-center justify-center mx-auto">
          <ClinicalIcon name="shield-check" size={32} ariaHidden="true" />
        </div>
        <h2 className="text-xl font-bold text-brand-text">Clinical Staff Access Required</h2>
        <p className="text-xs sm:text-sm text-brand-muted max-w-md mx-auto">
          The Doctor Consultation Queue Console is strictly restricted to authorized doctors and clinic administrators.
        </p>
        <div className="pt-2">
          <Button
            variant="primary"
            size="md"
            as={Link}
            to="/login"
            className="text-xs font-semibold"
          >
            Sign In as Clinical Staff
          </Button>
        </div>
      </div>
    )
  }

  // Doctor Profile Not Found Check (User is role="doctor" but has no doctor record)
  if (user.role === 'doctor' && doctorProfileNotFound) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-clinical-danger-border p-8 sm:p-12 text-center space-y-4 shadow-clinical-xs">
        <div className="w-16 h-16 rounded-2xl bg-clinical-danger-bg text-clinical-danger flex items-center justify-center mx-auto">
          <ClinicalIcon name="alert-circle" size={32} ariaHidden="true" />
        </div>
        <h2 className="text-xl font-bold text-brand-text">Doctor Profile Pending Setup</h2>
        <p className="text-xs sm:text-sm text-brand-muted max-w-md mx-auto">
          Your account has the doctor role, but your clinical practice profile is not linked to an active hospital. Please contact your hospital administrator.
        </p>
      </div>
    )
  }

  const waitingList = queueData?.waiting_list || []
  const hasCurrentConsultation = Boolean(currentConsultation)

  return (
    <div className="space-y-6">
      {/* Top Banner: Doctor Info, Facility, Stream Status & Doctor Switcher */}
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-7 shadow-clinical-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="teal" size="sm">
                <ClinicalIcon name="stethoscope" size={12} ariaHidden="true" />
                <span className="ml-1">Clinical Queue Console</span>
              </Badge>
              <Badge
                variant={isLive ? 'teal' : connectionMode === 'polling' ? 'warning' : 'neutral'}
                size="sm"
                dot={true}
              >
                {isLive ? 'Live WebSocket Active' : connectionMode === 'polling' ? 'Polling (10s)' : 'Connecting...'}
              </Badge>
              {lastRefreshed && (
                <span className="text-[11px] text-brand-muted">
                  Synced {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              )}
            </div>
            <h2 className="text-xl sm:text-2xl font-black text-brand-text tracking-tight">
              {queueData?.doctor_name ? `Dr. ${queueData.doctor_name}` : 'Doctor Console'}
            </h2>
            <p className="text-xs text-brand-muted">
              {queueData?.specialty} • {queueData?.hospital_name} • Date: {queueData?.queue_date}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Admin Doctor Switcher */}
            {['hospital_admin', 'system_admin'].includes(user.role) && (
              <div className="relative">
                <select
                  aria-label="Select Doctor Queue"
                  value={activeDoctorId}
                  onChange={(e) => setActiveDoctorId(e.target.value)}
                  disabled={isLoadingDoctors || isSubmittingAction}
                  className="bg-brand-ground hover:bg-stone-200 text-brand-text text-xs font-semibold rounded-xl border border-brand-border px-3.5 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-brand-accent transition-all cursor-pointer"
                >
                  {doctorsList.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      Dr. {doc.full_name} ({doc.specialty})
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-brand-muted text-xs">
                  <ClinicalIcon name="chevron-down" size={12} ariaHidden="true" />
                </div>
              </div>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => refresh()}
              className="text-xs font-semibold gap-1.5"
            >
              <ClinicalIcon name="refresh" size={13} ariaHidden="true" />
              <span>Refresh</span>
            </Button>
          </div>
        </div>

        {/* Global Feedback Banners */}
        {actionSuccess && (
          <div
            role="status"
            className="p-3.5 rounded-2xl bg-clinical-success-bg border border-clinical-success-border text-xs font-medium text-clinical-success flex items-center gap-2"
          >
            <ClinicalIcon name="check-circle" size={16} ariaHidden="true" />
            <span>{actionSuccess}</span>
          </div>
        )}

        {actionError && (
          <div
            role="alert"
            className="p-3.5 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs font-medium text-clinical-danger flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-2">
              <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
              <span>{actionError}</span>
            </div>
            <button
              type="button"
              onClick={() => setActionError(null)}
              className="p-1 rounded text-clinical-danger hover:opacity-75 transition-opacity"
            >
              <ClinicalIcon name="x" size={14} ariaHidden="true" />
            </button>
          </div>
        )}

        {queueError && !actionError && (
          <div
            role="alert"
            className="p-3.5 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs font-medium text-clinical-danger flex items-center justify-between gap-3"
          >
            <div className="flex items-center gap-2">
              <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
              <span>{queueError}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refresh()}
              className="text-xs font-bold"
            >
              Retry
            </Button>
          </div>
        )}
      </div>

      {/* 4 Metric Statistics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Waiting */}
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-4 sm:p-5 shadow-clinical-xs space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Patients Waiting
          </span>
          <div className="font-mono text-3xl sm:text-4xl font-extrabold text-brand-primary">
            {queueData?.total_waiting ?? 0}
          </div>
          <span className="text-[11px] text-brand-muted block">In reception line</span>
        </div>

        {/* Active Consultation */}
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-4 sm:p-5 shadow-clinical-xs space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Active in Room
          </span>
          <div className="font-mono text-3xl sm:text-4xl font-extrabold text-clinical-success">
            {hasCurrentConsultation ? 1 : 0}
          </div>
          <span className="text-[11px] text-brand-muted block">
            {hasCurrentConsultation ? `Token #${currentConsultation.token_number}` : 'Room vacant'}
          </span>
        </div>

        {/* Completed */}
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-4 sm:p-5 shadow-clinical-xs space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Completed Today
          </span>
          <div className="font-mono text-3xl sm:text-4xl font-extrabold text-brand-text">
            {queueData?.total_completed ?? 0}
          </div>
          <span className="text-[11px] text-brand-muted block">Consultations finished</span>
        </div>

        {/* Skipped */}
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-4 sm:p-5 shadow-clinical-xs space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Skipped / No-Shows
          </span>
          <div className="font-mono text-3xl sm:text-4xl font-extrabold text-brand-muted">
            {queueData?.total_skipped ?? 0}
          </div>
          <span className="text-[11px] text-brand-muted block">Eligible for recall</span>
        </div>
      </div>

      {/* Hero Section: Currently Serving in Room */}
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-8 shadow-clinical-xs space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-brand-border/70">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                hasCurrentConsultation ? 'bg-clinical-success animate-pulse' : 'bg-stone-300'
              }`}
            />
            <h3 className="text-sm font-bold uppercase tracking-wider text-brand-text">
              Current Patient in Consultation
            </h3>
          </div>
          {hasCurrentConsultation && (
            <Badge variant="teal" size="sm">
              <ClinicalIcon name="clock" size={11} ariaHidden="true" />
              <span className="ml-1 font-mono font-bold">{formatTimer(elapsedSeconds)}</span>
            </Badge>
          )}
        </div>

        {hasCurrentConsultation ? (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Token Display Box */}
              <div className="p-6 rounded-2xl bg-brand-deep text-white shadow-clinical-sm flex flex-col justify-between space-y-3">
                <span className="text-[11px] font-bold uppercase tracking-wider text-teal-200">
                  Active Token
                </span>
                <div>
                  <div className="font-mono text-5xl font-black tracking-tight select-all">
                    {currentConsultation.token_display}
                  </div>
                  <p className="text-xs text-teal-200 mt-1">
                    Token #{currentConsultation.token_number}
                  </p>
                </div>
                <div className="text-[11px] font-mono text-teal-200 pt-2 border-t border-white/15">
                  Ref: {currentConsultation.appointment_token}
                </div>
              </div>

              {/* Patient Metadata Card */}
              <div className="md:col-span-2 p-6 rounded-2xl bg-brand-ground border border-brand-border flex flex-col justify-between space-y-4">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted">
                    Patient Details
                  </span>
                  <h4 className="text-lg font-bold text-brand-text">
                    {currentConsultation.patient_name}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-brand-muted pt-1">
                    <div>
                      Scheduled Slot:{' '}
                      <span className="font-bold text-brand-text">
                        {currentConsultation.appointment_time}
                      </span>
                    </div>
                    {currentConsultation.patient_phone && (
                      <div>
                        Phone:{' '}
                        <span className="font-semibold text-brand-text">
                          {currentConsultation.patient_phone}
                        </span>
                      </div>
                    )}
                    {currentConsultation.patient_email && (
                      <div>
                        Email:{' '}
                        <span className="font-semibold text-brand-text truncate block">
                          {currentConsultation.patient_email}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Consultation Notes Input */}
                <div className="space-y-1.5 pt-2 border-t border-brand-border/70">
                  <label
                    htmlFor="active-consultation-notes"
                    className="block text-xs font-bold text-brand-text uppercase tracking-wider"
                  >
                    Clinical Observations / Notes (Optional)
                  </label>
                  <textarea
                    id="active-consultation-notes"
                    rows="2"
                    value={consultationNotes}
                    onChange={(e) => setConsultationNotes(e.target.value)}
                    placeholder="Enter diagnostic summary, prescriptions, or notes before completing consultation..."
                    maxLength={1000}
                    disabled={isSubmittingAction}
                    className="w-full px-3.5 py-2 rounded-xl border border-brand-border bg-brand-surface text-xs text-brand-text placeholder-brand-muted focus:outline-none focus:ring-2 focus:ring-brand-accent/20 focus:border-brand-accent transition-all resize-none"
                  />
                </div>
              </div>
            </div>

            {/* Consultation Action Triggers */}
            <div className="pt-2 flex flex-wrap items-center justify-end gap-3 border-t border-brand-border/70">
              <Button
                variant="outline"
                size="md"
                onClick={() => handleSkipPatient(currentConsultation)}
                disabled={isSubmittingAction}
                className="text-xs font-semibold text-clinical-danger border-clinical-danger/30 hover:bg-clinical-danger-bg hover:text-clinical-danger"
              >
                Skip / Mark No-Show
              </Button>

              <Button
                variant="primary"
                size="md"
                onClick={handleCompleteConsultation}
                isLoading={isSubmittingAction}
                className="text-xs font-bold gap-1.5"
              >
                <ClinicalIcon name="check" size={14} ariaHidden="true" />
                <span>Complete Consultation</span>
              </Button>
            </div>
          </div>
        ) : (
          <div className="py-8 text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-brand-ground text-brand-primary flex items-center justify-center mx-auto border border-brand-border">
              <ClinicalIcon name="user-doctor" size={28} ariaHidden="true" />
            </div>
            <div className="space-y-1">
              <h4 className="text-base font-bold text-brand-text">Consultation Room Ready</h4>
              <p className="text-xs text-brand-muted max-w-sm mx-auto">
                No patient is currently in the consultation room. Call the next patient in line when ready.
              </p>
            </div>
            <Button
              variant="primary"
              size="md"
              onClick={handleCallNext}
              disabled={waitingList.length === 0 || isSubmittingAction}
              isLoading={isSubmittingAction}
              className="text-xs font-bold gap-1.5"
            >
              <ClinicalIcon name="arrow-right" size={14} ariaHidden="true" />
              <span>Call Next Patient ({waitingList[0]?.token_display || 'Queue Empty'})</span>
            </Button>
          </div>
        )}
      </div>

      {/* Waiting List & Skipped Patients Section */}
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-8 shadow-clinical-xs space-y-6">
        {/* Tabs for Waiting Queue vs Skipped Patients */}
        <div className="flex items-center justify-between pb-4 border-b border-brand-border/70">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('waiting')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'waiting'
                  ? 'bg-brand-primary text-white shadow-clinical-xs'
                  : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
              }`}
            >
              Waiting Queue ({waitingList.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('skipped')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'skipped'
                  ? 'bg-brand-primary text-white shadow-clinical-xs'
                  : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
              }`}
            >
              Skipped Patients ({skippedHistory.length})
            </button>
          </div>

          <span className="text-xs text-brand-muted hidden sm:inline">
            Ordered by check-in sequence
          </span>
        </div>

        {/* Tab 1: Waiting Queue List */}
        {activeTab === 'waiting' && (
          <div>
            {isLoadingQueue ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton.Card key={i} lines={2} />
                ))}
              </div>
            ) : waitingList.length === 0 ? (
              <EmptyState
                icon="ticket"
                title="Waiting Queue is Empty"
                description="No patients are currently waiting in reception for this doctor's clinic."
              />
            ) : (
              <div className="space-y-3">
                {waitingList.map((item) => (
                  <div
                    key={item.id}
                    className="p-4 rounded-2xl bg-brand-ground border border-brand-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all hover:bg-stone-100/70"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      {/* Position Chip */}
                      <div className="w-9 h-9 rounded-xl bg-brand-surface border border-brand-border text-brand-text font-bold text-xs flex items-center justify-center shrink-0">
                        #{item.position}
                      </div>

                      {/* Token & Patient Name */}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-base font-extrabold text-brand-text">
                            {item.token_display}
                          </span>
                          <span className="font-semibold text-xs text-brand-text truncate">
                            {item.patient_name}
                          </span>
                        </div>
                        <p className="text-[11px] text-brand-muted truncate">
                          Slot: {item.appointment_time} • Ref: {item.appointment_token}
                        </p>
                      </div>
                    </div>

                    {/* Actions per waiting row */}
                    <div className="flex items-center gap-2 shrink-0 ml-auto sm:ml-0">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSkipPatient(item)}
                        disabled={isSubmittingAction}
                        className="text-xs font-semibold text-clinical-danger hover:bg-clinical-danger-bg hover:text-clinical-danger"
                      >
                        Skip
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCallSpecificPatient(item.id)}
                        disabled={hasCurrentConsultation || isSubmittingAction}
                        className="text-xs font-bold gap-1.5"
                      >
                        <ClinicalIcon name="arrow-right" size={12} ariaHidden="true" />
                        <span>Call Patient</span>
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Skipped Patients List (Recallable) */}
        {activeTab === 'skipped' && (
          <div>
            {skippedHistory.length === 0 ? (
              <EmptyState
                icon="user"
                title="No Skipped Patients"
                description="No patients have been marked as skipped or no-shows in this active session."
              />
            ) : (
              <div className="space-y-3">
                {skippedHistory.map((skippedItem) => (
                  <div
                    key={skippedItem.id}
                    className="p-4 rounded-2xl bg-brand-ground border border-brand-border flex items-center justify-between gap-4"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-extrabold text-brand-text">
                          {skippedItem.token_display}
                        </span>
                        <span className="font-semibold text-xs text-brand-text">
                          {skippedItem.patient_name}
                        </span>
                        <Badge variant="warning" size="sm">
                          Skipped
                        </Badge>
                      </div>
                      <p className="text-[11px] text-brand-muted">
                        Slot: {skippedItem.appointment_time}
                      </p>
                    </div>

                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleRecallPatient(skippedItem.id)}
                      disabled={isSubmittingAction}
                      className="text-xs font-bold gap-1.5"
                    >
                      <ClinicalIcon name="refresh" size={12} ariaHidden="true" />
                      <span>Recall to Queue</span>
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
