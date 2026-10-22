import React, { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  getMyQueueEntry,
  checkInQueue,
  cancelQueueEntry,
  getDoctorById,
  predictWaitingTime,
} from '../../services/api'
import { useQueueSocket } from '../../hooks/useQueueSocket'
import { playChime } from '../../utils/sound'

export default function PatientQueueTracker() {
  const [activeEntry, setActiveEntry] = useState(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [fetchError, setFetchError] = useState(null)

  // Check-in form state
  const [checkInToken, setCheckInToken] = useState('')
  const [isCheckingIn, setIsCheckingIn] = useState(false)
  const [checkInError, setCheckInError] = useState(null)

  // Cancellation state
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [cancelError, setCancelError] = useState(null)

  // Audio cue state tracking
  const alertedPositionRef = useRef(null)

  // ML Waiting-Time Prediction State (Phase 6.6)
  const [mlPrediction, setMlPrediction] = useState(null)
  const [mlLoading, setMlLoading] = useState(false)
  const [mlUnavailable, setMlUnavailable] = useState(false)
  const doctorCacheRef = useRef({})

  // Fetch ML waiting-time prediction when active entry is in waiting state
  useEffect(() => {
    let isMounted = true

    // Only query when active entry is waiting and has required IDs
    if (!activeEntry || activeEntry.status !== 'waiting' || !activeEntry.doctor_id) {
      return
    }

    const loadPrediction = async () => {
      Promise.resolve().then(() => {
        if (isMounted) {
          setMlLoading(true)
          setMlUnavailable(false)
        }
      })

      try {
        // Fetch or use cached doctor metadata
        let doc = doctorCacheRef.current[activeEntry.doctor_id]
        if (!doc) {
          doc = await getDoctorById(activeEntry.doctor_id)
          if (doc) doctorCacheRef.current[activeEntry.doctor_id] = doc
        }

        // Strict validation: Never invent missing features
        if (!doc || !doc.specialty || doc.experience_years == null || !activeEntry.appointment_time) {
          if (isMounted) {
            setMlPrediction(null)
            setMlLoading(false)
          }
          return
        }

        const [slotH, slotM] = activeEntry.appointment_time.split(':').map((v) => parseInt(v, 10))
        if (isNaN(slotH) || isNaN(slotM)) {
          if (isMounted) {
            setMlPrediction(null)
            setMlLoading(false)
          }
          return
        }

        const qDate = activeEntry.queue_date ? new Date(activeEntry.queue_date) : new Date()
        const rawDay = qDate.getDay()
        const dayOfWeek = rawDay === 0 ? 6 : rawDay - 1

        let arrivalLead = 0.0
        if (activeEntry.checked_in_at && activeEntry.appointment_time) {
          const apptDt = new Date(
            `${activeEntry.queue_date || new Date().toISOString().slice(0, 10)}T${activeEntry.appointment_time}:00`
          )
          const checkInDt = new Date(activeEntry.checked_in_at)
          const diffMinutes = (apptDt - checkInDt) / 60000
          if (!isNaN(diffMinutes)) {
            arrivalLead = Math.max(-180.0, Math.min(180.0, Math.round(diffMinutes)))
          }
        }

        const payload = {
          doctor_specialty: doc.specialty,
          doctor_experience_years: Math.max(0, Math.min(70, parseInt(doc.experience_years, 10) || 0)),
          day_of_week: dayOfWeek,
          slot_hour: Math.max(0, Math.min(23, slotH)),
          slot_minute: Math.max(0, Math.min(59, slotM)),
          arrival_lead_minutes: arrivalLead,
          queue_position_at_checkin: Math.max(1, activeEntry.token_number || activeEntry.position || 1),
          patients_waiting_ahead: Math.max(0, (activeEntry.position || 1) - 1),
          is_doctor_active_consultation: activeEntry.position > 1 ? 1 : 0,
          historical_avg_consultation_minutes: 15.0,
        }

        const pred = await predictWaitingTime(payload)
        if (isMounted) {
          setMlPrediction(pred)
          setMlUnavailable(false)
        }
      } catch {
        if (isMounted) {
          setMlPrediction(null)
          setMlUnavailable(true)
        }
      } finally {
        if (isMounted) {
          setMlLoading(false)
        }
      }
    }

    loadPrediction()

    return () => {
      isMounted = false
    }
  }, [activeEntry])

  // Fetcher for active patient entry
  const fetchMyQueue = async () => {
    try {
      const res = await getMyQueueEntry()
      setActiveEntry(res)
      setFetchError(null)
      return res
    } catch (err) {
      if (err.status === 404) {
        // No active entry today - expected empty state
        setActiveEntry(null)
        setFetchError(null)
        return null
      }
      setFetchError(err.message || 'Unable to load queue status')
      throw err
    } finally {
      setInitialLoading(false)
    }
  }

  // Real-time hook connected to the doctor's channel if patient has an active entry
  const doctorId = activeEntry?.doctor_id || null
  const { isLive, connectionMode, lastRefreshed, refresh } = useQueueSocket({
    doctorId,
    fetcher: fetchMyQueue,
    enabled: true,
    pollingInterval: 10000,
    onEvent: (event) => {
      // If a patient was called, play notification chime if it matches patient
      if (event.action === 'PATIENT_CALLED') {
        playChime('call')
      }
    },
  })

  // Turn-approaching alert check (when position drops to <= 2)
  useEffect(() => {
    if (activeEntry && activeEntry.status === 'waiting') {
      const pos = activeEntry.position
      if (pos > 0 && pos <= 2 && alertedPositionRef.current !== pos) {
        alertedPositionRef.current = pos
        playChime('turn')
      }
    }
  }, [activeEntry])

  // Handle manual Check-in
  const handleCheckIn = async (e) => {
    e.preventDefault()
    if (!checkInToken.trim()) return

    setIsCheckingIn(true)
    setCheckInError(null)
    try {
      const entry = await checkInQueue({ appointment_token: checkInToken.trim() })
      setActiveEntry(entry)
      setCheckInToken('')
      refresh()
    } catch (err) {
      setCheckInError(err.message || 'Failed to check in. Please verify your token.')
    } finally {
      setIsCheckingIn(false)
    }
  }

  // Handle Cancel Queue Entry
  const handleCancelEntry = async () => {
    if (!activeEntry) return

    setIsCancelling(true)
    setCancelError(null)
    try {
      await cancelQueueEntry(activeEntry.id)
      setActiveEntry(null)
      setShowCancelConfirm(false)
      refresh()
    } catch (err) {
      setCancelError(err.message || 'Failed to cancel queue entry')
    } finally {
      setIsCancelling(false)
    }
  }

  // Stepper calculations
  const getStepStatus = (stepName) => {
    if (!activeEntry) return 'upcoming'
    const status = activeEntry.status

    if (status === 'cancelled') {
      return stepName === 'cancelled' ? 'current' : 'upcoming'
    }
    if (status === 'skipped') {
      return stepName === 'skipped' ? 'current' : 'upcoming'
    }

    switch (stepName) {
      case 'checked_in':
        return 'completed'
      case 'waiting':
        if (status === 'waiting') return 'current'
        if (['in_consultation', 'completed'].includes(status)) return 'completed'
        return 'upcoming'
      case 'in_consultation':
        if (status === 'in_consultation') return 'current'
        if (status === 'completed') return 'completed'
        return 'upcoming'
      case 'completed':
        return status === 'completed' ? 'completed' : 'upcoming'
      default:
        return 'upcoming'
    }
  }

  // Initial loading state
  if (initialLoading) {
    return (
      <div className="bg-white rounded-3xl border border-slate-200/80 p-8 shadow-sm text-center space-y-4 animate-pulse">
        <div className="w-14 h-14 bg-teal-50 rounded-2xl mx-auto flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
        </div>
        <div className="h-5 bg-slate-100 rounded-md w-48 mx-auto" />
        <div className="h-4 bg-slate-100 rounded-md w-64 mx-auto" />
      </div>
    )
  }

  // Error state
  if (fetchError && !activeEntry) {
    return (
      <div className="bg-white rounded-3xl border border-rose-200 p-8 shadow-sm text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto text-xl">
          ⚠️
        </div>
        <h3 className="text-lg font-bold text-slate-900">Unable to load queue status</h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto">{fetchError}</p>
        <button
          type="button"
          onClick={() => {
            setInitialLoading(true)
            refresh()
          }}
          className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow-sm transition-all"
        >
          Try Again
        </button>
      </div>
    )
  }

  // Empty state: Patient has no active queue entry today
  if (!activeEntry) {
    return (
      <div className="bg-white rounded-3xl border border-slate-200/80 p-8 shadow-sm space-y-8">
        <div className="text-center max-w-lg mx-auto space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-2xl shadow-inner shadow-teal-700/10">
            🎟️
          </div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">No Active Queue Entry Today</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            You do not have a live token in the clinic queue for today. If you have an appointment booked for today, check in below using your appointment reference token.
          </p>
        </div>

        {/* Check-In Form */}
        <div className="max-w-md mx-auto p-6 rounded-2xl bg-gradient-to-br from-slate-50 to-teal-50/30 border border-slate-200/80 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-700 uppercase tracking-wider">
            <span>Clinic Self Check-In</span>
          </div>

          <form onSubmit={handleCheckIn} className="space-y-3">
            <div>
              <label htmlFor="token-input" className="block text-xs font-semibold text-slate-700 mb-1">
                Appointment Tracking Token
              </label>
              <input
                id="token-input"
                type="text"
                placeholder="e.g. MS-20261020-A1B2"
                value={checkInToken}
                onChange={(e) => setCheckInToken(e.target.value.toUpperCase())}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white font-mono text-sm tracking-wide text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all uppercase"
                disabled={isCheckingIn}
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                Find this on your appointment confirmation card.
              </span>
            </div>

            {checkInError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700">
                {checkInError}
              </div>
            )}

            <button
              type="submit"
              disabled={isCheckingIn || !checkInToken.trim()}
              className="w-full py-2.5 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 disabled:opacity-50 text-white text-xs font-bold tracking-wide shadow-sm shadow-teal-700/20 transition-all flex items-center justify-center gap-2"
            >
              {isCheckingIn ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Checking In...</span>
                </>
              ) : (
                <span>Check In to Today's Queue →</span>
              )}
            </button>
          </form>

          <div className="pt-2 text-center">
            <Link
              to="/appointments"
              className="text-xs font-semibold text-teal-700 hover:text-teal-800 underline underline-offset-2"
            >
              View My Scheduled Appointments
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // Active Queue Entry View
  const isTurnApproaching = activeEntry.position > 0 && activeEntry.position <= 2 && activeEntry.status === 'waiting'
  const isInConsultation = activeEntry.status === 'in_consultation'
  const isCompleted = activeEntry.status === 'completed'
  const isSkipped = activeEntry.status === 'skipped'
  const currentMlPrediction = activeEntry.status === 'waiting' ? mlPrediction : null

  return (
    <div className="space-y-6">
      {/* Turn Approaching Banner */}
      {isTurnApproaching && (
        <div className="p-5 rounded-3xl bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 text-white shadow-lg shadow-orange-500/20 flex flex-col sm:flex-row items-center justify-between gap-4 animate-bounce-subtle">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-2xl shrink-0">
              🔔
            </div>
            <div>
              <h4 className="font-extrabold text-base tracking-tight">Your Turn is Approaching!</h4>
              <p className="text-xs text-amber-100 mt-0.5">
                You are {activeEntry.position === 1 ? 'next in line' : `${activeEntry.position}nd in line`}. Please remain near Dr. {activeEntry.doctor_name}&apos;s consultation room.
              </p>
            </div>
          </div>
          <span className="text-xs font-bold uppercase tracking-wider bg-white/20 px-3 py-1.5 rounded-full border border-white/30 shrink-0">
            Get Ready
          </span>
        </div>
      )}

      {/* Main Queue Dashboard Card */}
      <div className="bg-white rounded-3xl border border-slate-200/80 p-6 sm:p-8 shadow-sm space-y-8">
        {/* Top Header with Live Indicator & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                isLive
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : connectionMode === 'polling'
                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isLive ? 'bg-emerald-500 animate-pulse' : connectionMode === 'polling' ? 'bg-amber-500' : 'bg-slate-400'
                }`}
              />
              {isLive ? 'Live WebSocket Stream' : connectionMode === 'polling' ? 'Polling Mode (10s)' : 'Reconnecting...'}
            </span>

            {lastRefreshed && (
              <span className="text-[11px] text-slate-400">
                Updated {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => refresh()}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-50 border border-slate-200/80 transition-all text-xs font-semibold flex items-center gap-1.5"
              title="Refresh Queue State"
            >
              <span>↻</span> Refresh
            </button>

            {!isInConsultation && !isCompleted && (
              <button
                type="button"
                onClick={() => setShowCancelConfirm(true)}
                className="px-3 py-2 rounded-xl text-xs font-semibold text-rose-600 hover:bg-rose-50 border border-rose-200 transition-all"
              >
                Cancel Queue Entry
              </button>
            )}
          </div>
        </div>

        {/* Hero Token & Position Display */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Your Token */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-teal-500 to-cyan-600 text-white shadow-md shadow-teal-700/15 flex flex-col justify-between space-y-4">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-100">
              Your Daily Token
            </span>
            <div className="space-y-1">
              <span className="font-mono text-5xl font-black tracking-tight">{activeEntry.token_display}</span>
              <p className="text-xs text-teal-100 font-medium">Token #{activeEntry.token_number} for Today</p>
            </div>
            <div className="text-[11px] font-mono text-teal-100/90 pt-2 border-t border-teal-400/30">
              Ref: {activeEntry.appointment_token}
            </div>
          </div>

          {/* Card 2: Current Position */}
          <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between space-y-4">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Queue Position
            </span>
            <div className="space-y-1">
              {isInConsultation ? (
                <div>
                  <span className="text-2xl font-black text-emerald-600">IN CONSULTATION</span>
                  <p className="text-xs text-slate-500 mt-1">Doctor is examining you right now</p>
                </div>
              ) : isCompleted ? (
                <div>
                  <span className="text-2xl font-black text-blue-600">COMPLETED</span>
                  <p className="text-xs text-slate-500 mt-1">Your consultation has concluded</p>
                </div>
              ) : isSkipped ? (
                <div>
                  <span className="text-2xl font-black text-amber-600">SKIPPED</span>
                  <p className="text-xs text-slate-500 mt-1">Please report to reception</p>
                </div>
              ) : (
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-5xl font-black text-slate-900 tracking-tight">
                      {activeEntry.position}
                    </span>
                    <span className="text-sm font-bold text-slate-400 uppercase">in line</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    {activeEntry.position === 1 ? 'You are next!' : `${activeEntry.position - 1} patient(s) ahead`}
                  </p>
                </div>
              )}
            </div>
            <span className="text-xs font-semibold text-slate-400 pt-2 border-t border-slate-200/60">
              Live Dynamic Position
            </span>
          </div>

          {/* Card 3: Estimated Wait Time (Phase 6.6 ML Enhanced) */}
          <div className="p-6 rounded-2xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Est. Waiting Time
              </span>
              {currentMlPrediction && !isInConsultation && !isCompleted && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-100 text-teal-800 border border-teal-200">
                  🤖 AI Estimate
                </span>
              )}
            </div>

            <div className="space-y-1">
              {isInConsultation ? (
                <div className="flex items-baseline gap-2 text-emerald-600">
                  <span className="text-4xl font-black tracking-tight">Active</span>
                </div>
              ) : isCompleted ? (
                <div className="text-blue-600">
                  <span className="text-4xl font-black tracking-tight">0 min</span>
                </div>
              ) : mlLoading ? (
                <div className="space-y-2 py-1">
                  <div className="h-10 w-28 bg-slate-200 animate-pulse rounded-lg"></div>
                  <p className="text-[11px] text-slate-400">Calculating AI queue pace...</p>
                </div>
              ) : currentMlPrediction ? (
                <div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-5xl font-black text-teal-900 tracking-tight">
                      ~{currentMlPrediction.predicted_wait_minutes}
                    </span>
                    <span className="text-sm font-bold text-teal-700 uppercase">
                      {currentMlPrediction.unit || 'mins'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Powered by <span className="font-semibold text-slate-700">{currentMlPrediction.model_name}</span> (v{currentMlPrediction.model_version})
                  </p>
                </div>
              ) : (
                <div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-5xl font-black text-slate-900 tracking-tight">
                      ~{activeEntry.estimated_wait_minutes ?? (Math.max(0, activeEntry.position - 1) * 15)}
                    </span>
                    <span className="text-sm font-bold text-slate-400 uppercase">mins</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    {mlUnavailable ? 'Standard queue heuristic (AI model offline)' : 'Standard clinic heuristic (15 min / patient)'}
                  </p>
                </div>
              )}
            </div>

            {/* Provenance Disclosure / Notice */}
            <div className="pt-2 border-t border-slate-200/60">
              {currentMlPrediction && !isInConsultation && !isCompleted ? (
                <p className="text-[10px] text-amber-800/90 bg-amber-50/70 px-2 py-1 rounded-lg border border-amber-200/60">
                  ⚠️ <strong>Demonstration Only:</strong> Trained on synthetic queue data; not clinically calibrated.
                </p>
              ) : (
                <span className="text-xs font-semibold text-slate-400">
                  Standard Clinic Estimate
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Doctor and Clinic Info Banner */}
        <div className="p-5 rounded-2xl bg-slate-50/80 border border-slate-200/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-100/70 text-teal-800 flex items-center justify-center font-bold text-sm">
              Dr
            </div>
            <div>
              <h4 className="font-bold text-slate-900 text-sm">{activeEntry.doctor_name}</h4>
              <p className="text-xs text-slate-500">
                {activeEntry.hospital_name} • Scheduled Slot: {activeEntry.appointment_time || 'Clinic Hours'}
              </p>
            </div>
          </div>
          <div className="text-xs text-slate-500">
            Queue Date: <span className="font-semibold text-slate-700">{activeEntry.queue_date}</span>
          </div>
        </div>

        {/* Progress Stepper */}
        <div className="space-y-4">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Consultation Progress
          </h4>
          <div className="grid grid-cols-4 gap-2 text-center">
            {/* Step 1 */}
            <div className="space-y-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('checked_in') === 'completed' ? 'bg-teal-600' : 'bg-slate-200'
                }`}
              />
              <span className="text-xs font-bold text-slate-800 block">1. Checked In</span>
              <span className="text-[10px] text-slate-400 block">Token Allocated</span>
            </div>

            {/* Step 2 */}
            <div className="space-y-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('waiting') === 'completed'
                    ? 'bg-teal-600'
                    : getStepStatus('waiting') === 'current'
                    ? 'bg-amber-500 animate-pulse'
                    : 'bg-slate-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('waiting') === 'current' ? 'text-amber-600' : 'text-slate-800'
                }`}
              >
                2. Waiting
              </span>
              <span className="text-[10px] text-slate-400 block">In Queue</span>
            </div>

            {/* Step 3 */}
            <div className="space-y-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('in_consultation') === 'completed'
                    ? 'bg-teal-600'
                    : getStepStatus('in_consultation') === 'current'
                    ? 'bg-emerald-500 animate-pulse'
                    : 'bg-slate-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('in_consultation') === 'current' ? 'text-emerald-600' : 'text-slate-800'
                }`}
              >
                3. Consultation
              </span>
              <span className="text-[10px] text-slate-400 block">With Doctor</span>
            </div>

            {/* Step 4 */}
            <div className="space-y-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('completed') === 'completed' ? 'bg-blue-600' : 'bg-slate-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('completed') === 'completed' ? 'text-blue-600' : 'text-slate-800'
                }`}
              >
                4. Completed
              </span>
              <span className="text-[10px] text-slate-400 block">Done</span>
            </div>
          </div>
        </div>
      </div>

      {/* Cancellation Confirmation Modal */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 max-w-md w-full shadow-2xl space-y-6">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center text-xl mx-auto">
              ⚠️
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-lg font-bold text-slate-900">Cancel Queue Position?</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Cancelling will release your token <span className="font-mono font-bold text-slate-800">{activeEntry.token_display}</span> and cancel your scheduled consultation slot for today. This action cannot be undone.
              </p>
            </div>

            {cancelError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700">
                {cancelError}
              </div>
            )}

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setShowCancelConfirm(false)}
                disabled={isCancelling}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-all"
              >
                Keep My Token
              </button>
              <button
                type="button"
                onClick={handleCancelEntry}
                disabled={isCancelling}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-sm shadow-rose-700/20 transition-all flex items-center justify-center gap-2"
              >
                {isCancelling ? 'Cancelling...' : 'Yes, Cancel Position'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
