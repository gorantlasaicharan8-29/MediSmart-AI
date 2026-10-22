import React, { useState, useEffect } from 'react'
import { predictNoShow } from '../../services/api'

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
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-400 border border-slate-200 animate-pulse">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-300"></span>
        AI Risk Analysis...
      </span>
    )
  }

  const { risk_band, no_show_probability, decision_threshold, model_name } = prediction
  const pct = Math.round(no_show_probability * 100)

  let badgeColor = 'bg-teal-50 text-teal-700 border-teal-200'
  let dotColor = 'bg-teal-500'
  let label = 'Low'

  if (risk_band === 'high') {
    badgeColor = 'bg-rose-50 text-rose-700 border-rose-200'
    dotColor = 'bg-rose-500'
    label = 'Elevated'
  } else if (risk_band === 'moderate') {
    badgeColor = 'bg-amber-50 text-amber-700 border-amber-200'
    dotColor = 'bg-amber-500'
    label = 'Moderate'
  }

  return (
    <div className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setShowTooltip((prev) => !prev)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold border transition-all cursor-pointer ${badgeColor}`}
        title="Click for synthetic ML prediction details"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`}></span>
        <span>Attendance Risk: {label} ({pct}%)</span>
        <span className="text-[9px] opacity-75 font-mono">ⓘ</span>
      </button>

      {/* Popover Card */}
      {showTooltip && (
        <div className="absolute left-0 mt-1 z-30 w-72 p-3 bg-white rounded-xl shadow-lg border border-slate-200 text-xs space-y-2 animate-in fade-in zoom-in-95 duration-100">
          <div className="flex items-center justify-between font-bold text-slate-800 pb-1.5 border-b border-slate-100">
            <span>🤖 Attendance Predictability</span>
            <button
              type="button"
              onClick={() => setShowTooltip(false)}
              className="text-slate-400 hover:text-slate-600 text-sm leading-none p-0.5"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1 text-[11px] text-slate-600">
            <p>
              Probability of absence: <span className="font-bold text-slate-800">{pct}%</span>
            </p>
            <p>
              Risk band: <span className="font-semibold capitalize text-slate-800">{risk_band}</span>
            </p>
            <p className="text-[10px] text-slate-400">
              Evaluated via {model_name} (Operating threshold: {decision_threshold.toFixed(2)})
            </p>
          </div>
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-200 text-[10px] text-amber-900 leading-snug">
            ⚠️ <strong>Synthetic Demonstration:</strong> Generated for scheduling flow simulation. Not a clinical assessment.
          </div>
        </div>
      )}
    </div>
  )
}
