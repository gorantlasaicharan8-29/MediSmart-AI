import React, { useState, useEffect, useRef, useCallback } from 'react'
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
import {
  Button,
  Badge,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Skeleton,
  EmptyState,
  ClinicalIcon,
} from '../ui'

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
  const [copiedToken, setCopiedToken] = useState(false)

  // Audio cue state tracking
  const alertedPositionRef = useRef(null)

  // ML Waiting-Time Prediction State
  const [mlPrediction, setMlPrediction] = useState(null)
  const [mlLoading, setMlLoading] = useState(false)
  const [mlUnavailable, setMlUnavailable] = useState(false)
  const doctorCacheRef = useRef({})

  // Fetch ML waiting-time prediction when active entry is in waiting state
  useEffect(() => {
    let isMounted = true

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
        let doc = doctorCacheRef.current[activeEntry.doctor_id]
        if (!doc) {
          doc = await getDoctorById(activeEntry.doctor_id)
          if (doc) doctorCacheRef.current[activeEntry.doctor_id] = doc
        }

        // Strict feature contract: Never invent missing features
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
  const fetchMyQueue = useCallback(async () => {
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
  }, [])

  // Real-time hook connected to the doctor's channel if patient has an active entry
  const doctorId = activeEntry?.doctor_id || null
  const { isLive, connectionMode, lastRefreshed, refresh } = useQueueSocket({
    doctorId,
    fetcher: fetchMyQueue,
    enabled: true,
    pollingInterval: 10000,
    onEvent: (event) => {
      // If a patient was called, play notification chime
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
      setCheckInError(err.message || 'Failed to check in. Please verify your appointment token.')
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

  // Copy token to clipboard
  const handleCopyRefToken = () => {
    if (activeEntry?.appointment_token) {
      navigator.clipboard.writeText(activeEntry.appointment_token)
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
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
      <div className="space-y-4">
        <Skeleton.Card lines={4} />
      </div>
    )
  }

  // Error state
  if (fetchError && !activeEntry) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-clinical-danger-border p-8 shadow-clinical-xs text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-clinical-danger-bg text-clinical-danger flex items-center justify-center mx-auto">
          <ClinicalIcon name="alert-circle" size={24} ariaHidden="true" />
        </div>
        <h3 className="text-lg font-bold text-brand-text">Unable to Load Queue Status</h3>
        <p className="text-xs text-brand-muted max-w-md mx-auto">{fetchError}</p>
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            setInitialLoading(true)
            refresh()
          }}
          className="text-xs font-bold"
        >
          Try Again
        </Button>
      </div>
    )
  }

  // Empty state: Patient has no active queue entry today
  if (!activeEntry) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-10 shadow-clinical-xs space-y-8">
        <EmptyState
          icon="ticket"
          title="No Active Queue Entry Today"
          description="You do not currently have a live token in the clinic queue. If you have an appointment booked for today, enter your unique appointment reference token below to check in."
        />

        {/* Self Check-In Form */}
        <div className="max-w-md mx-auto p-6 rounded-2xl bg-brand-ground border border-brand-border space-y-4">
          <div className="flex items-center gap-2 text-xs font-bold text-brand-text uppercase tracking-wider">
            <ClinicalIcon name="ticket" size={14} className="text-brand-primary" ariaHidden="true" />
            <span>Clinic Self Check-In</span>
          </div>

          <form onSubmit={handleCheckIn} className="space-y-3.5">
            <div>
              <Input
                label="Appointment Reference Token"
                id="checkin-token-input"
                type="text"
                placeholder="e.g. MS-20261025-A1B2"
                value={checkInToken}
                onChange={(e) => setCheckInToken(e.target.value.toUpperCase())}
                disabled={isCheckingIn}
                helperText="Found on your appointment booking confirmation."
                className="font-mono text-sm tracking-wide uppercase"
              />
            </div>

            {checkInError && (
              <div
                role="alert"
                className="p-3 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs font-medium text-clinical-danger flex items-center gap-2"
              >
                <ClinicalIcon name="alert-circle" size={14} ariaHidden="true" />
                <span>{checkInError}</span>
              </div>
            )}

            <Button
              variant="primary"
              size="md"
              type="submit"
              disabled={isCheckingIn || !checkInToken.trim()}
              isLoading={isCheckingIn}
              className="w-full text-xs font-bold justify-center"
            >
              Check In to Today&apos;s Queue
            </Button>
          </form>

          <div className="pt-2 text-center">
            <Link
              to="/appointments"
              className="text-xs font-semibold text-brand-primary hover:text-brand-accent underline underline-offset-2"
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
        <div
          role="alert"
          aria-live="polite"
          className="p-5 rounded-2xl bg-clinical-warning-bg border border-clinical-warning-border text-clinical-warning shadow-clinical-sm flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-amber-500/10 border border-amber-500/20 text-clinical-warning flex items-center justify-center shrink-0">
              <ClinicalIcon name="alert-triangle" size={22} ariaHidden="true" />
            </div>
            <div>
              <h4 className="font-extrabold text-sm sm:text-base tracking-tight">Your Turn is Approaching!</h4>
              <p className="text-xs text-brand-muted mt-0.5">
                You are {activeEntry.position === 1 ? 'next in line' : `${activeEntry.position}nd in line`}. Please remain near Dr. {activeEntry.doctor_name}&apos;s consultation room.
              </p>
            </div>
          </div>
          <Badge variant="warning" size="md">
            Please Stand By
          </Badge>
        </div>
      )}

      {/* In Consultation Banner */}
      {isInConsultation && (
        <div
          role="alert"
          aria-live="polite"
          className="p-5 rounded-2xl bg-clinical-success-bg border border-clinical-success-border text-clinical-success shadow-clinical-sm flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-clinical-success flex items-center justify-center shrink-0">
              <ClinicalIcon name="check-circle" size={24} ariaHidden="true" />
            </div>
            <div>
              <h4 className="font-extrabold text-sm sm:text-base tracking-tight">Active Consultation in Progress</h4>
              <p className="text-xs text-brand-muted mt-0.5">
                Dr. {activeEntry.doctor_name} is consulting with you. Please proceed inside the room.
              </p>
            </div>
          </div>
          <Badge variant="success" size="md" dot={true}>
            In Room Now
          </Badge>
        </div>
      )}

      {/* Main Queue Card */}
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-8 shadow-clinical-xs space-y-6">
        {/* Header with Live Indicator & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-brand-border/70">
          <div className="flex items-center gap-3 flex-wrap">
            <Badge
              variant={isLive ? 'teal' : connectionMode === 'polling' ? 'warning' : 'neutral'}
              size="sm"
              dot={true}
            >
              {isLive
                ? 'Live WebSocket Connected'
                : connectionMode === 'polling'
                ? 'Polling Mode (10s)'
                : 'Reconnecting...'}
            </Badge>

            {lastRefreshed && (
              <span className="text-[11px] text-brand-muted">
                Synced {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refresh()}
              className="text-xs font-semibold gap-1.5"
            >
              <ClinicalIcon name="refresh" size={13} ariaHidden="true" />
              <span>Refresh</span>
            </Button>

            {!isInConsultation && !isCompleted && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCancelConfirm(true)}
                className="text-xs font-semibold text-clinical-danger hover:bg-clinical-danger-bg hover:text-clinical-danger"
              >
                Cancel Queue Entry
              </Button>
            )}
          </div>
        </div>

        {/* 3 Metric Cards: Token, Position, Waiting Time */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Card 1: Your Daily Token */}
          <div className="p-5 rounded-2xl bg-brand-deep text-white shadow-clinical-sm flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-teal-200">
                Your Daily Token
              </span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/10 text-teal-100">
                Today
              </span>
            </div>
            <div className="space-y-1">
              <span className="font-mono text-4xl sm:text-5xl font-black tracking-tight select-all">
                {activeEntry.token_display}
              </span>
              <p className="text-xs text-teal-200 font-medium">
                Token #{activeEntry.token_number}
              </p>
            </div>
            <div className="pt-2 border-t border-white/15 flex items-center justify-between text-[11px] font-mono text-teal-200">
              <span className="truncate">Ref: {activeEntry.appointment_token}</span>
              <button
                type="button"
                onClick={handleCopyRefToken}
                className="p-1 rounded text-teal-200 hover:text-white transition-colors cursor-pointer"
                title="Copy appointment reference token"
                aria-label="Copy reference token"
              >
                <ClinicalIcon name={copiedToken ? 'check' : 'copy'} size={12} ariaHidden="true" />
              </button>
            </div>
          </div>

          {/* Card 2: Current Position */}
          <div className="p-5 rounded-2xl bg-brand-ground border border-brand-border flex flex-col justify-between space-y-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted">
              Live Queue Position
            </span>
            <div className="space-y-1">
              {isInConsultation ? (
                <div>
                  <span className="text-2xl font-black text-clinical-success">IN CONSULTATION</span>
                  <p className="text-xs text-brand-muted mt-1">Doctor is consulting with you now</p>
                </div>
              ) : isCompleted ? (
                <div>
                  <span className="text-2xl font-black text-clinical-info">COMPLETED</span>
                  <p className="text-xs text-brand-muted mt-1">Your consultation has concluded</p>
                </div>
              ) : isSkipped ? (
                <div>
                  <span className="text-2xl font-black text-clinical-warning">SKIPPED</span>
                  <p className="text-xs text-brand-muted mt-1">Please report to reception counter</p>
                </div>
              ) : (
                <div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-4xl sm:text-5xl font-black text-brand-text tracking-tight">
                      #{activeEntry.position}
                    </span>
                    <span className="text-xs font-bold text-brand-muted uppercase">in line</span>
                  </div>
                  <p className="text-xs text-brand-muted mt-1">
                    {activeEntry.position === 1 ? 'You are next in line!' : `${activeEntry.position - 1} patient(s) ahead of you`}
                  </p>
                </div>
              )}
            </div>
            <span className="text-[11px] font-semibold text-brand-muted pt-2 border-t border-brand-border/70">
              Updated Live via WebSocket
            </span>
          </div>

          {/* Card 3: Estimated Wait Time */}
          <div className="p-5 rounded-2xl bg-brand-ground border border-brand-border flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted">
                Est. Waiting Time
              </span>
              {currentMlPrediction && !isInConsultation && !isCompleted && (
                <Badge variant="teal" size="sm">
                  <ClinicalIcon name="sparkles" size={10} ariaHidden="true" />
                  <span className="ml-1 text-[10px]">AI Estimate</span>
                </Badge>
              )}
            </div>

            <div className="space-y-1">
              {isInConsultation ? (
                <div className="text-clinical-success">
                  <span className="text-3xl font-black">In Room</span>
                </div>
              ) : isCompleted ? (
                <div className="text-brand-muted">
                  <span className="text-3xl font-black">0 min</span>
                </div>
              ) : mlLoading ? (
                <div className="space-y-2 py-1">
                  <Skeleton className="h-8 w-28 rounded-lg" />
                  <p className="text-[11px] text-brand-muted animate-pulse">Calculating queue pace...</p>
                </div>
              ) : currentMlPrediction ? (
                <div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-4xl sm:text-5xl font-black text-brand-primary tracking-tight">
                      ~{currentMlPrediction.predicted_wait_minutes}
                    </span>
                    <span className="text-xs font-bold text-brand-primary uppercase">
                      {currentMlPrediction.unit || 'mins'}
                    </span>
                  </div>
                  <p className="text-xs text-brand-muted mt-1">
                    Evaluated by <span className="font-semibold text-brand-text">{currentMlPrediction.model_name}</span>
                  </p>
                </div>
              ) : (
                <div>
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-4xl sm:text-5xl font-black text-brand-text tracking-tight">
                      ~{activeEntry.estimated_wait_minutes ?? (Math.max(0, activeEntry.position - 1) * 15)}
                    </span>
                    <span className="text-xs font-bold text-brand-muted uppercase">mins</span>
                  </div>
                  <p className="text-xs text-brand-muted mt-1">
                    {mlUnavailable ? 'Standard queue heuristic (AI service offline)' : 'Standard clinic heuristic (15m pace)'}
                  </p>
                </div>
              )}
            </div>

            {/* Provenance Disclosure */}
            <div className="pt-2 border-t border-brand-border/70">
              {currentMlPrediction && !isInConsultation && !isCompleted ? (
                <p className="text-[10px] text-clinical-warning bg-clinical-warning-bg px-2 py-1 rounded-lg border border-clinical-warning-border">
                  <strong>Estimate Notice:</strong> Dynamic approximation; not a guaranteed start time.
                </p>
              ) : (
                <span className="text-[11px] font-semibold text-brand-muted">
                  Estimated Clinic Duration
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Doctor and Clinic Info Banner */}
        <div className="p-4 rounded-2xl bg-brand-ground border border-brand-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-mint text-brand-deep flex items-center justify-center font-bold text-sm border border-teal-200">
              <ClinicalIcon name="user-doctor" size={18} ariaHidden="true" />
            </div>
            <div>
              <h4 className="font-bold text-brand-text text-sm">{activeEntry.doctor_name}</h4>
              <p className="text-xs text-brand-muted">
                {activeEntry.hospital_name} • Scheduled Slot: {activeEntry.appointment_time || 'Clinic Hours'}
              </p>
            </div>
          </div>
          <div className="text-xs text-brand-muted">
            Queue Date: <span className="font-semibold text-brand-text">{activeEntry.queue_date}</span>
          </div>
        </div>

        {/* Progress Stepper */}
        <div className="space-y-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Consultation Progress
          </span>
          <div className="grid grid-cols-4 gap-2 text-center">
            {/* Step 1 */}
            <div className="space-y-1.5">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('checked_in') === 'completed' ? 'bg-brand-primary' : 'bg-stone-200'
                }`}
              />
              <span className="text-xs font-bold text-brand-text block">1. Checked In</span>
              <span className="text-[10px] text-brand-muted block">Token Allocated</span>
            </div>

            {/* Step 2 */}
            <div className="space-y-1.5">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('waiting') === 'completed'
                    ? 'bg-brand-primary'
                    : getStepStatus('waiting') === 'current'
                    ? 'bg-clinical-warning animate-pulse'
                    : 'bg-stone-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('waiting') === 'current' ? 'text-clinical-warning' : 'text-brand-text'
                }`}
              >
                2. Waiting
              </span>
              <span className="text-[10px] text-brand-muted block">In Queue</span>
            </div>

            {/* Step 3 */}
            <div className="space-y-1.5">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('in_consultation') === 'completed'
                    ? 'bg-brand-primary'
                    : getStepStatus('in_consultation') === 'current'
                    ? 'bg-clinical-success animate-pulse'
                    : 'bg-stone-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('in_consultation') === 'current' ? 'text-clinical-success' : 'text-brand-text'
                }`}
              >
                3. Consultation
              </span>
              <span className="text-[10px] text-brand-muted block">With Doctor</span>
            </div>

            {/* Step 4 */}
            <div className="space-y-1.5">
              <div
                className={`h-2 rounded-full transition-all ${
                  getStepStatus('completed') === 'completed' ? 'bg-clinical-info' : 'bg-stone-200'
                }`}
              />
              <span
                className={`text-xs font-bold block ${
                  getStepStatus('completed') === 'completed' ? 'text-clinical-info' : 'text-brand-text'
                }`}
              >
                4. Completed
              </span>
              <span className="text-[10px] text-brand-muted block">Concluded</span>
            </div>
          </div>
        </div>
      </div>

      {/* Cancellation Confirmation Modal */}
      <Modal
        isOpen={showCancelConfirm}
        onClose={() => !isCancelling && setShowCancelConfirm(false)}
        size="md"
        showCloseButton={false}
      >
        <ModalHeader
          onClose={() => !isCancelling && setShowCancelConfirm(false)}
          showCloseButton={!isCancelling}
        >
          <div className="space-y-1">
            <Badge variant="danger" size="sm">
              <ClinicalIcon name="alert-triangle" size={12} ariaHidden="true" />
              <span className="ml-1">Cancellation Confirmation</span>
            </Badge>
            <h2 className="text-base font-bold text-brand-text">
              Cancel Queue Position?
            </h2>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-4">
          <p className="text-xs text-brand-muted leading-relaxed">
            Cancelling will release your daily queue token{' '}
            <span className="font-mono font-bold text-brand-text">{activeEntry.token_display}</span> and cancel your scheduled consultation slot for today. This action cannot be undone.
          </p>

          {cancelError && (
            <div
              role="alert"
              className="p-3 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center gap-2"
            >
              <ClinicalIcon name="alert-circle" size={14} ariaHidden="true" />
              <span>{cancelError}</span>
            </div>
          )}
        </ModalBody>

        <ModalFooter>
          <Button
            variant="ghost"
            size="md"
            disabled={isCancelling}
            onClick={() => setShowCancelConfirm(false)}
            className="text-xs font-semibold"
          >
            Keep My Token
          </Button>
          <Button
            variant="danger"
            size="md"
            onClick={handleCancelEntry}
            isLoading={isCancelling}
            className="text-xs font-bold"
          >
            Yes, Cancel Position
          </Button>
        </ModalFooter>
      </Modal>
    </div>
  )
}
