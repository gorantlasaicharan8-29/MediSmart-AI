import React, { useState, useEffect } from 'react'
import { predictNoShow } from '../../services/api'
import { Badge, ClinicalIcon } from '../ui'

export default function NoShowRiskBadge({ appointment, priorStats = null }) {
  const [prediction, setPrediction] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)

  const isScheduled = appointment?.status === 'scheduled'

  useEffect(() => {
    let isMounted = true

    if (!isScheduled || !appointment?.appointment_date || !appointment?.appointment_time) {
      return
    }

    const specialty = appointment.doctor?.specialty
    if (!specialty) {
      // Never invent missing features
      return
    }

    const apptDate = new Date(appointment.appointment_date)
    const createdAt = appointment.created_at ? new Date(appointment.created_at) : new Date()

    const rawDay = apptDate.getDay()
    const dayOfWeek = rawDay === 0 ? 6 : rawDay - 1
    const isWeekend = dayOfWeek === 5 || dayOfWeek === 6 ? 1 : 0

    const slotHour = parseInt(
      typeof appointment.appointment_time === 'string'
        ? appointment.appointment_time.slice(0, 2)
        : '10',
      10
    )

    const diffDays = Math.round((apptDate - createdAt) / (1000 * 60 * 60 * 24))
    const leadTimeDays = Math.max(0, isNaN(diffDays) ? 0 : diffDays)

    const fee = typeof appointment.doctor?.consultation_fee === 'number'
      ? appointment.doctor.consultation_fee
      : 500.0

    const priorAppointments = priorStats?.priorCount ?? 0
    const priorNoShows = priorStats?.priorNoShows ?? 0
    const priorRate = priorStats?.priorRate ?? 0.0

    const payload = {
      doctor_specialty: specialty,
      lead_time_days: Math.min(365, leadTimeDays),
      day_of_week: dayOfWeek,
      slot_hour: Math.max(0, Math.min(23, isNaN(slotHour) ? 10 : slotHour)),
      is_weekend: isWeekend,
      consultation_fee: Math.max(0, fee),
      patient_prior_appointments: Math.max(0, priorAppointments),
      patient_prior_no_shows: Math.max(0, priorNoShows),
      patient_prior_no_show_rate: Math.max(0.0, Math.min(1.0, priorRate)),
      has_notes: appointment.notes && appointment.notes.trim().length > 0 ? 1 : 0,
    }

    Promise.resolve().then(() => {
      if (isMounted) setIsLoading(true)
    })

    predictNoShow(payload)
      .then((res) => {
        if (isMounted) {
          setPrediction(res)
        }
      })
      .catch(() => {
        if (isMounted) {
          setPrediction(null)
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [
    isScheduled,
    appointment?.id,
    appointment?.appointment_date,
    appointment?.appointment_time,
    appointment?.created_at,
    appointment?.notes,
    appointment?.doctor?.specialty,
    appointment?.doctor?.consultation_fee,
    priorStats?.priorCount,
    priorStats?.priorNoShows,
    priorStats?.priorRate,
  ])

  if (!isScheduled || (!prediction && !isLoading)) {
    return null
  }

  if (isLoading) {
    return (
      <Badge variant="neutral" size="sm" className="animate-pulse">
        <ClinicalIcon name="clock" size={10} ariaHidden="true" />
        <span className="ml-1 text-[10px]">AI Risk Analysis...</span>
      </Badge>
    )
  }

  const { risk_band, no_show_probability, decision_threshold, model_name } = prediction
  const pct = Math.round(no_show_probability * 100)

  let badgeVariant = 'teal'
  let label = 'Low Risk'

  if (risk_band === 'high') {
    badgeVariant = 'danger'
    label = 'Elevated Risk'
  } else if (risk_band === 'moderate') {
    badgeVariant = 'warning'
    label = 'Moderate Risk'
  }

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setShowTooltip((prev) => !prev)}
        className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent rounded-full"
        title="View synthetic ML attendance prediction details"
        aria-expanded={showTooltip}
      >
        <Badge
          variant={badgeVariant}
          size="sm"
          dot={true}
          className="hover:opacity-90 transition-opacity"
        >
          <span>Attendance: {label} ({pct}%)</span>
          <ClinicalIcon name="info" size={11} className="ml-1 opacity-70" ariaHidden="true" />
        </Badge>
      </button>

      {/* Popover Card */}
      {showTooltip && (
        <div
          role="dialog"
          aria-label="Attendance Predictability Details"
          className="absolute left-0 mt-2 z-30 w-72 p-3.5 bg-brand-surface rounded-2xl shadow-clinical-lg border border-brand-border text-xs space-y-2.5 animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="flex items-center justify-between font-bold text-brand-text pb-1.5 border-b border-brand-border/70">
            <div className="flex items-center gap-1.5">
              <ClinicalIcon name="sparkles" size={14} className="text-brand-accent" ariaHidden="true" />
              <span>Attendance Predictability</span>
            </div>
            <button
              type="button"
              onClick={() => setShowTooltip(false)}
              className="text-brand-muted hover:text-brand-text p-0.5 rounded transition-colors"
              aria-label="Close prediction details"
            >
              <ClinicalIcon name="x" size={14} ariaHidden="true" />
            </button>
          </div>

          <div className="space-y-1 text-[11px] text-brand-muted">
            <div className="flex justify-between">
              <span>Estimated absence probability:</span>
              <span className="font-bold text-brand-text">{pct}%</span>
            </div>
            <div className="flex justify-between">
              <span>Classified risk tier:</span>
              <span className="font-semibold capitalize text-brand-text">{risk_band}</span>
            </div>
            <p className="text-[10px] text-brand-muted pt-1">
              Evaluated via {model_name} (Threshold: {decision_threshold.toFixed(2)})
            </p>
          </div>

          <div className="p-2 rounded-xl bg-clinical-warning-bg border border-clinical-warning-border text-[10px] text-clinical-warning leading-snug">
            <strong>Synthetic Demonstration:</strong> Generated for scheduling flow simulation. Not a clinical assessment.
          </div>
        </div>
      )}
    </div>
  )
}
