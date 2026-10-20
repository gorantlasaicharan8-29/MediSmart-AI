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
      <div className="rounded-3xl border border-slate-200 bg-white p-8 sm:p-12 text-center space-y-4 shadow-sm">
        <div className="w-16 h-16 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto text-3xl">
          🔒
        </div>
        <h2 className="text-xl font-bold text-slate-900">Clinical Staff Access Required</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          The Doctor Consultation Queue Console is strictly restricted to authorized doctors and clinic administrators.
        </p>
        <div className="pt-2">
          <Link
            to="/login"
            className="inline-flex px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow-sm transition-all"
          >
            Sign in as Clinical Staff
          </Link>
        </div>
      </div>
    )
  }

  // Doctor Profile Not Found Check (User is role="doctor" but has no doctors table record)
  if (user.role === 'doctor' && doctorProfileNotFound) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-white p-8 sm:p-12 text-center space-y-4 shadow-sm">
        <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto text-3xl">
          👨‍⚕️
        </div>
        <h2 className="text-xl font-bold text-slate-900">No Doctor Profile Linked</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Your account is registered as a Doctor, but no matching professional clinic record was found. Please contact hospital administration to associate your profile.
        </p>
      </div>
    )
  }

  const waitingList = queueData?.waiting_list || []

  return (
    <div className="space-y-6">
      {/* Top Banner: Doctor Info, Scoping Selector, Connection State */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-600">
              Doctor Consultation Console
            </span>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                isLive
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : connectionMode === 'polling'
                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isLive
                    ? 'bg-emerald-500 animate-pulse'
                    : connectionMode === 'polling'
                    ? 'bg-amber-500'
                    : 'bg-slate-400'
                }`}
              />
              {isLive ? 'LIVE' : connectionMode === 'polling' ? 'POLLING (10s)' : 'RECONNECTING'}
            </span>
          </div>

          <h2 className="text-2xl font-black text-slate-900 tracking-tight">
            {queueData?.doctor_name ? `Dr. ${queueData.doctor_name}` : `Dr. ${user.full_name}`}
          </h2>
          <p className="text-xs text-slate-500">
            {queueData?.specialty || 'Clinical Specialist'} • {queueData?.hospital_name || 'Hospital Facility'} • Today: {queueData?.queue_date || 'Clinic Hours'}
          </p>
        </div>

        {/* Doctor Selector for Hospital/System Admins & Refresh Trigger */}
        <div className="flex flex-wrap items-center gap-3">
          {['hospital_admin', 'system_admin'].includes(user.role) && (
            <div className="relative">
              <label htmlFor="admin-doc-select" className="sr-only">
                Switch Doctor Queue
              </label>
              <select
                id="admin-doc-select"
                value={activeDoctorId}
                onChange={(e) => {
                  setActiveDoctorId(e.target.value)
                  setIsLoadingQueue(true)
                }}
                disabled={isLoadingDoctors}
                className="bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-semibold rounded-xl border border-slate-200 px-3.5 py-2.5 pr-8 focus:outline-none focus:ring-2 focus:ring-teal-500 transition-all appearance-none cursor-pointer"
              >
                {doctorsList.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    Dr. {doc.full_name} ({doc.specialty})
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-slate-400 text-xs">
                ▼
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={() => refresh()}
            className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-600 transition-all text-xs font-semibold flex items-center gap-1.5"
            title="Refresh Queue Now"
          >
            <span>↻</span> Refresh
          </button>
        </div>
      </div>

      {/* Global Alerts: Error or Success Feedback */}
      {actionError && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-800 flex items-start justify-between gap-3 animate-fade-in">
          <div className="flex items-start gap-2">
            <span className="text-base leading-none">⚠️</span>
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-rose-500 hover:text-rose-700 text-sm font-bold leading-none"
          >
            ✕
          </button>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs font-medium text-emerald-800 flex items-center justify-between gap-3 animate-fade-in">
          <div className="flex items-center gap-2">
            <span className="text-base leading-none">✓</span>
            <span>{actionSuccess}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccess(null)}
            className="text-emerald-500 hover:text-emerald-700 text-sm font-bold leading-none"
          >
            ✕
          </button>
        </div>
      )}

      {/* Queue Error Banner */}
      {queueError && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs font-medium text-amber-800 flex items-center justify-between gap-3">
          <span>{queueError}</span>
          <button
            type="button"
            onClick={() => refresh()}
            className="underline font-bold text-amber-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* KPI Metric Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Total Waiting */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              Waiting in Queue
            </span>
            <span className="text-3xl font-black text-slate-900 font-mono mt-1 block">
              {queueData?.total_waiting ?? 0}
            </span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center text-xl">
            👥
          </div>
        </div>

        {/* Metric 2: Currently In Consultation */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              In Consultation
            </span>
            <span className="text-3xl font-black text-emerald-600 font-mono mt-1 block">
              {currentConsultation ? 1 : 0}
            </span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
            🩺
          </div>
        </div>

        {/* Metric 3: Completed Today */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              Completed Today
            </span>
            <span className="text-3xl font-black text-blue-600 font-mono mt-1 block">
              {queueData?.total_completed ?? 0}
            </span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
            ✓
          </div>
        </div>

        {/* Metric 4: Skipped Today */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">
              Skipped / No-Show
            </span>
            <span className="text-3xl font-black text-amber-600 font-mono mt-1 block">
              {queueData?.total_skipped ?? 0}
            </span>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
            ⏭
          </div>
        </div>
      </div>

      {/* Main Grid: Active Consultation Workspace (Hero) vs Queue List */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* ACTIVE CONSULTATION WORKSPACE (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Active Examination Workspace
            </h3>
            {currentConsultation && (
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                Duration: {formatTimer(elapsedSeconds)}
              </span>
            )}
          </div>

          {isLoadingQueue && !queueData ? (
            <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center space-y-3">
              <div className="w-8 h-8 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-xs font-semibold text-slate-400">Loading consultation room...</p>
            </div>
          ) : currentConsultation ? (
            /* Patient In Consultation Card */
            <div className="bg-gradient-to-br from-slate-900 via-slate-850 to-slate-950 text-white rounded-3xl p-6 sm:p-8 shadow-xl border border-slate-800 space-y-6">
              {/* Header inside hero */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-black uppercase tracking-wider">
                    In Examination
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    Token #{currentConsultation.token_number}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  Scheduled: <span className="text-slate-200 font-semibold">{currentConsultation.appointment_time || 'Clinic Hours'}</span>
                </div>
              </div>

              {/* Patient Info & Big Token */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
                <div className="space-y-1">
                  <div className="font-mono text-5xl font-black text-white tracking-tight text-teal-400">
                    {currentConsultation.token_display}
                  </div>
                  <h4 className="text-xl font-bold text-white pt-1">
                    {currentConsultation.patient_name}
                  </h4>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 pt-1">
                    {currentConsultation.patient_phone && (
                      <span>📞 {currentConsultation.patient_phone}</span>
                    )}
                    {currentConsultation.patient_email && (
                      <span>✉️ {currentConsultation.patient_email}</span>
                    )}
                  </div>
                  <div className="text-[11px] font-mono text-slate-500 pt-1">
                    Ref: {currentConsultation.appointment_token}
                  </div>
                </div>

                {/* Live Clock / Stop Watch Visual */}
                <div className="text-center p-4 rounded-2xl bg-slate-800/80 border border-slate-700/60 sm:min-w-[140px]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    Elapsed Time
                  </span>
                  <span className="text-2xl font-black font-mono text-emerald-400 mt-0.5 block">
                    {formatTimer(elapsedSeconds)}
                  </span>
                </div>
              </div>

              {/* Clinical Consultation Notes Input */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label
                  htmlFor="consultation-notes"
                  className="block text-xs font-semibold text-slate-300"
                >
                  Clinical Examination Notes / Instructions (Optional)
                </label>
                <textarea
                  id="consultation-notes"
                  rows={3}
                  value={consultationNotes}
                  onChange={(e) => setConsultationNotes(e.target.value)}
                  placeholder="Record symptoms, diagnosis, recommendations, or patient advice..."
                  className="w-full px-4 py-2.5 rounded-2xl bg-slate-800/90 border border-slate-700 text-slate-100 text-xs placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500 transition-all resize-none"
                  disabled={isSubmittingAction}
                />
              </div>

              {/* Action Buttons: Complete vs Skip */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCompleteConsultation}
                  disabled={isSubmittingAction}
                  className="flex-1 py-3 rounded-2xl bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-600 hover:to-emerald-700 disabled:opacity-50 text-white text-xs font-bold shadow-md shadow-emerald-900/30 transition-all flex items-center justify-center gap-2"
                >
                  {isSubmittingAction ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Updating...</span>
                    </>
                  ) : (
                    <>
                      <span>✓</span>
                      <span>Complete Consultation</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => handleSkipPatient(currentConsultation)}
                  disabled={isSubmittingAction}
                  className="px-5 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-amber-400 border border-slate-700 text-xs font-bold transition-all"
                  title="Mark patient as No-Show / Skipped"
                >
                  ⏭ Skip Patient
                </button>
              </div>
            </div>
          ) : (
            /* Empty State: No active patient in consultation */
            <div className="bg-white rounded-3xl border border-slate-200/80 p-8 sm:p-12 text-center space-y-4 shadow-sm">
              <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center text-3xl mx-auto shadow-inner shadow-teal-700/10">
                🩺
              </div>
              <div className="space-y-1">
                <h4 className="text-lg font-bold text-slate-900">Examination Room Ready</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  No patient is currently in consultation. Call the next patient in line when you are ready to begin.
                </p>
              </div>

              {waitingList.length > 0 ? (
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleCallNext}
                    disabled={isSubmittingAction}
                    className="px-6 py-3 rounded-2xl bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 disabled:opacity-50 text-white text-xs font-bold shadow-md shadow-teal-700/20 transition-all inline-flex items-center gap-2"
                  >
                    {isSubmittingAction ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Calling...</span>
                      </>
                    ) : (
                      <>
                        <span>📢</span>
                        <span>Call Next: {waitingList[0].token_display} ({waitingList[0].patient_name})</span>
                      </>
                    )}
                  </button>
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/60 text-xs text-slate-400 max-w-xs mx-auto">
                  All checked-in patients have been seen.
                </div>
              )}
            </div>
          )}
        </div>

        {/* QUEUE PATIENTS LIST (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="inline-flex p-1 rounded-xl bg-slate-100 border border-slate-200">
              <button
                type="button"
                onClick={() => setActiveTab('waiting')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                  activeTab === 'waiting'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Waiting ({waitingList.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('skipped')}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                  activeTab === 'skipped'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Skipped ({queueData?.total_skipped ?? 0})
              </button>
            </div>

            <span className="text-[11px] text-slate-400">
              Updated {lastRefreshed ? lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'recently'}
            </span>
          </div>

          {/* Tab 1: Waiting Patients List */}
          {activeTab === 'waiting' && (
            <div className="space-y-3">
              {waitingList.length === 0 ? (
                <div className="bg-white rounded-3xl border border-slate-200 p-8 text-center space-y-2">
                  <div className="text-2xl text-slate-400">✓</div>
                  <h4 className="text-xs font-bold text-slate-700">Waiting Queue is Clear</h4>
                  <p className="text-[11px] text-slate-400">
                    No other patients are currently waiting in the clinic lobby.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[580px] overflow-y-auto pr-1">
                  {waitingList.map((patient) => {
                    const isNextInLine = patient.position === 1
                    return (
                      <div
                        key={patient.id}
                        className={`p-4 rounded-2xl border transition-all ${
                          isNextInLine
                            ? 'bg-gradient-to-r from-teal-50/50 to-white border-teal-200 shadow-sm'
                            : 'bg-white border-slate-200/80 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3">
                            {/* Position number */}
                            <div
                              className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                                isNextInLine
                                  ? 'bg-teal-600 text-white'
                                  : 'bg-slate-100 text-slate-700'
                              }`}
                            >
                              {patient.position}
                            </div>

                            {/* Details */}
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-base font-black text-slate-900">
                                  {patient.token_display}
                                </span>
                                {isNextInLine && (
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 bg-teal-100/70 px-2 py-0.5 rounded-md">
                                    Next
                                  </span>
                                )}
                              </div>
                              <h5 className="font-bold text-slate-900 text-xs">
                                {patient.patient_name}
                              </h5>
                              <p className="text-[11px] text-slate-400">
                                Slot: {patient.appointment_time || 'Clinic Hours'} • Ref: {patient.appointment_token}
                              </p>
                            </div>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex flex-col sm:flex-row items-center gap-1.5 shrink-0">
                            <button
                              type="button"
                              onClick={() => handleCallSpecificPatient(patient.id)}
                              disabled={isSubmittingAction}
                              className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-[11px] font-bold shadow-sm transition-all flex items-center gap-1"
                              title="Call this patient into consultation"
                            >
                              <span>📢</span> Call
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSkipPatient(patient)}
                              disabled={isSubmittingAction}
                              className="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 text-[11px] font-semibold transition-all"
                              title="Skip patient"
                            >
                              Skip
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Skipped Patients */}
          {activeTab === 'skipped' && (
            <div className="space-y-3">
              {skippedHistory.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    Session Skipped Patients (Click to Recall)
                  </span>
                  {skippedHistory.map((item) => (
                    <div
                      key={item.id}
                      className="p-3.5 rounded-2xl bg-amber-50/60 border border-amber-200/80 flex items-center justify-between gap-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-xs text-amber-900">
                            {item.token_display}
                          </span>
                          <span className="text-xs font-semibold text-slate-800">
                            {item.patient_name}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400">
                          Slot: {item.appointment_time || 'Clinic Hours'}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRecallPatient(item.id)}
                        disabled={isSubmittingAction}
                        className="px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-[11px] font-bold shadow-sm transition-all"
                      >
                        ↩ Recall
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {queueData?.total_skipped === 0 && skippedHistory.length === 0 ? (
                <div className="bg-white rounded-3xl border border-slate-200 p-8 text-center space-y-2">
                  <div className="text-2xl text-slate-400">✓</div>
                  <h4 className="text-xs font-bold text-slate-700">No Skipped Patients</h4>
                  <p className="text-[11px] text-slate-400">
                    No patients have been marked as skipped today.
                  </p>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
                  <p className="text-xs text-slate-600">
                    Total skipped patients recorded on backend today:{' '}
                    <span className="font-bold text-slate-900">{queueData?.total_skipped ?? 0}</span>.
                  </p>
                  <p className="text-[11px] text-slate-400">
                    Recalled patients re-enter the waiting queue with status 'waiting' and retain their sequential token allocation.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
