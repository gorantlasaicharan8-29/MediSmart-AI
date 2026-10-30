import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  getDoctorClinicalQueue,
  callQueuePatient,
  completeQueuePatient,
  skipQueuePatient,
} from '../../services/api'
import { useQueueSocket } from '../../hooks/useQueueSocket'
import { playChime } from '../../utils/sound'
import { Button, ClinicalIcon, Skeleton } from '../ui'

export default function DoctorQueuePanel({ doctorId, onActionComplete }) {
  const [queueData, setQueueData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [actionSuccess, setActionSuccess] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  // Fetch full clinical queue for doctor
  const fetchQueue = useCallback(async () => {
    if (!doctorId) {
      setIsLoading(false)
      return null
    }
    try {
      const data = await getDoctorClinicalQueue(doctorId)
      setQueueData(data)
      setError(null)
      return data
    } catch (err) {
      setError(err.message || 'Unable to load clinical queue')
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [doctorId])

  // WebSocket with 10s automatic polling fallback
  const { isLive, connectionMode, refresh } = useQueueSocket({
    doctorId: doctorId || null,
    fetcher: fetchQueue,
    enabled: Boolean(doctorId),
    pollingInterval: 10000,
    onEvent: (event) => {
      if (event.action === 'CHECKED_IN') {
        playChime('turn')
      }
    },
  })

  // Timer for active consultation
  const currentConsultation = queueData?.current_consultation
  const calledAtTimestamp = currentConsultation?.called_at

  useEffect(() => {
    if (!calledAtTimestamp) {
      setElapsedSeconds(0)
      return
    }

    const calcElapsed = () => {
      const calledAt = new Date(calledAtTimestamp).getTime()
      const now = Date.now()
      setElapsedSeconds(Math.max(0, Math.floor((now - calledAt) / 1000)))
    }
    calcElapsed()
    const timer = setInterval(calcElapsed, 1000)
    return () => clearInterval(timer)
  }, [calledAtTimestamp])

  const formatTimer = (secs) => {
    const mins = Math.floor(secs / 60)
    const s = secs % 60
    return `${String(mins).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  const showFeedback = (msg) => {
    setActionSuccess(msg)
    setActionError(null)
    setTimeout(() => setActionSuccess(null), 4000)
  }

  // Action: Call Next Patient in Queue
  const handleCallNext = async () => {
    const nextPatient = queueData?.waiting_list?.[0]
    if (!nextPatient) return
    setIsSubmitting(true)
    setActionError(null)
    try {
      await callQueuePatient(nextPatient.id)
      showFeedback(`Called ${nextPatient.patient_name} (${nextPatient.token_display}) into consultation.`)
      await refresh()
      if (onActionComplete) onActionComplete()
    } catch (err) {
      setActionError(err.message || 'Failed to call patient')
      await refresh()
    } finally {
      setIsSubmitting(false)
    }
  }

  // Action: Complete Active Consultation
  const handleCompleteCurrent = async () => {
    if (!currentConsultation) return
    setIsSubmitting(true)
    setActionError(null)
    try {
      await completeQueuePatient(currentConsultation.id)
      showFeedback(`Consultation with ${currentConsultation.patient_name} marked as completed.`)
      await refresh()
      if (onActionComplete) onActionComplete()
    } catch (err) {
      setActionError(err.message || 'Failed to complete consultation')
      await refresh()
    } finally {
      setIsSubmitting(false)
    }
  }

  // Action: Skip Active Patient
  const handleSkipCurrent = async () => {
    if (!currentConsultation) return
    setIsSubmitting(true)
    setActionError(null)
    try {
      await skipQueuePatient(currentConsultation.id)
      showFeedback(`Patient ${currentConsultation.patient_name} skipped.`)
      await refresh()
      if (onActionComplete) onActionComplete()
    } catch (err) {
      setActionError(err.message || 'Failed to skip patient')
      await refresh()
    } finally {
      setIsSubmitting(false)
    }
  }

  // Up to next 3 waiting patients
  const upcomingPatients = queueData?.waiting_list || []
  const nextPatient = upcomingPatients[0] || null
  const waitingCount = queueData?.total_waiting || upcomingPatients.length || 0
  const estWaitMins = waitingCount * 15

  return (
    <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs space-y-5">
      {/* Panel Header */}
      <div className="flex items-center justify-between pb-3 border-b border-brand-border/70">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-brand-mint text-brand-deep flex items-center justify-center">
            <ClinicalIcon name="activity" size={16} />
          </div>
          <div>
            <h3 className="text-base font-bold text-brand-text leading-tight">
              Live Patient Queue
            </h3>
            <p className="text-[11px] text-brand-muted">
              Real-time consultation flow
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Live indicator badge */}
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold ${
              isLive
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isLive ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
              }`}
            />
            {isLive ? 'LIVE' : connectionMode === 'polling' ? 'SYNCING' : 'OFFLINE'}
          </span>

          <Link
            to="/doctor/queue"
            className="text-xs font-semibold text-brand-primary hover:text-brand-deep hover:underline transition-colors ml-1"
          >
            Full Console &rarr;
          </Link>
        </div>
      </div>

      {/* Action Feedback Messages */}
      {actionSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2 animate-fadeIn">
          <ClinicalIcon name="check" size={14} className="text-emerald-600 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}
      {actionError && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs flex items-center gap-2 animate-fadeIn">
          <ClinicalIcon name="alert" size={14} className="text-red-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="space-y-3 py-2">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50/60 border border-red-100 rounded-2xl text-center space-y-2">
          <p className="text-xs text-red-700">{error}</p>
          <Button size="sm" variant="outline" onClick={fetchQueue}>
            Retry Queue Sync
          </Button>
        </div>
      ) : (
        <>
          {/* Current Consultation Card */}
          {currentConsultation ? (
            <div className="relative rounded-2xl bg-gradient-to-br from-teal-50/90 to-emerald-50/50 border border-teal-200 p-4 space-y-3 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-teal-600 text-white text-[10px] font-bold uppercase tracking-wider">
                  <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                  In Consultation
                </span>
                <span className="text-xs font-mono font-bold text-teal-900 bg-white/80 px-2 py-0.5 rounded-md border border-teal-200">
                  Elapsed: {formatTimer(elapsedSeconds)}
                </span>
              </div>

              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-xl font-extrabold text-brand-text">
                      {currentConsultation.token_display}
                    </span>
                    <span className="text-sm font-bold text-brand-text truncate">
                      {currentConsultation.patient_name}
                    </span>
                  </div>
                  <p className="text-[11px] text-brand-muted mt-0.5">
                    Appointment: {currentConsultation.appointment_time || 'Clinic Slot'} &bull; Ref: {currentConsultation.appointment_token || 'N/A'}
                  </p>
                </div>
              </div>

              {/* Consultation Control Actions */}
              <div className="flex items-center gap-2 pt-1">
                <Button
                  size="sm"
                  variant="primary"
                  className="flex-1 text-xs py-2 bg-brand-primary hover:bg-brand-deep text-white font-bold shadow-xs cursor-pointer"
                  onClick={handleCompleteCurrent}
                  disabled={isSubmitting}
                >
                  <ClinicalIcon name="check" size={14} className="mr-1.5" />
                  Complete Consultation
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs py-2 text-brand-muted hover:text-red-700 hover:border-red-200 hover:bg-red-50 cursor-pointer"
                  onClick={handleSkipCurrent}
                  disabled={isSubmitting}
                >
                  Skip
                </Button>
              </div>
            </div>
          ) : (
            /* No patient in consultation */
            <div className="rounded-2xl border border-dashed border-brand-border bg-brand-ground/60 p-4 text-center space-y-2">
              <div className="w-10 h-10 rounded-full bg-teal-50 text-brand-primary mx-auto flex items-center justify-center">
                <ClinicalIcon name="stethoscope" size={20} />
              </div>
              <div>
                <p className="text-xs font-bold text-brand-text">
                  Doctor Ready for Next Patient
                </p>
                <p className="text-[11px] text-brand-muted">
                  No consultation currently in progress
                </p>
              </div>

              {nextPatient ? (
                <div className="pt-2">
                  <Button
                    size="sm"
                    variant="primary"
                    className="w-full text-xs py-2.5 bg-brand-primary hover:bg-brand-deep text-white font-bold shadow-xs cursor-pointer"
                    onClick={handleCallNext}
                    disabled={isSubmitting}
                  >
                    <ClinicalIcon name="users" size={14} className="mr-1.5" />
                    Call Next Patient ({nextPatient.token_display} &bull; {nextPatient.patient_name})
                  </Button>
                </div>
              ) : (
                <p className="text-[11px] text-brand-muted italic pt-1">
                  Queue is clear. No waiting patients.
                </p>
              )}
            </div>
          )}

          {/* Queue Snapshot Metrics */}
          <div className="grid grid-cols-3 gap-2 text-center pt-1">
            <div className="p-2.5 bg-brand-ground rounded-xl border border-brand-border/60">
              <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider block">
                Waiting
              </span>
              <span className="text-lg font-extrabold text-brand-text">
                {waitingCount}
              </span>
            </div>
            <div className="p-2.5 bg-brand-ground rounded-xl border border-brand-border/60">
              <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider block">
                Next Token
              </span>
              <span className="text-lg font-extrabold text-brand-accent">
                {nextPatient?.token_display || '—'}
              </span>
            </div>
            <div className="p-2.5 bg-brand-ground rounded-xl border border-brand-border/60">
              <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider block">
                Est. Wait
              </span>
              <span className="text-lg font-extrabold text-brand-text">
                {estWaitMins}m
              </span>
            </div>
          </div>

          {/* Upcoming In Line (Preview) */}
          {upcomingPatients.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-brand-border/60">
              <div className="flex items-center justify-between text-xs font-bold text-brand-muted">
                <span>Next in Line</span>
                <span>{upcomingPatients.length} queued</span>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {upcomingPatients.slice(0, 4).map((pt, idx) => (
                  <div
                    key={pt.id}
                    className="flex items-center justify-between p-2 rounded-xl bg-white border border-brand-border/70 hover:border-brand-primary/40 transition-colors text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-5 h-5 rounded-full bg-brand-ground text-brand-text font-bold text-[10px] flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>
                      <span className="font-mono font-bold text-brand-deep">
                        {pt.token_display}
                      </span>
                      <span className="text-brand-text font-medium truncate">
                        {pt.patient_name}
                      </span>
                    </div>

                    {!currentConsultation && idx === 0 && (
                      <Button
                        size="xs"
                        variant="outline"
                        className="text-[10px] py-0.5 px-2 text-brand-primary border-brand-primary/40 hover:bg-brand-mint/50"
                        onClick={handleCallNext}
                        disabled={isSubmitting}
                      >
                        Call
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
