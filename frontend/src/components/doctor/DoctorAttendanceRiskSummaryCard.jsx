import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getDoctorAppointmentsRisk } from '../../services/api'
import { Badge, Button, ClinicalIcon, Skeleton } from '../ui'

export default function DoctorAttendanceRiskSummaryCard({ doctorId = null, reloadKey = 0 }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadRiskSummary = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await getDoctorAppointmentsRisk({ doctorId })
      setData(res)
    } catch (err) {
      setError(err.message || 'Unable to load appointment risk analytics')
    } finally {
      setIsLoading(false)
    }
  }, [doctorId])

  useEffect(() => {
    loadRiskSummary()
  }, [loadRiskSummary, reloadKey])

  if (isLoading) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs animate-pulse space-y-4">
        <Skeleton className="h-5 w-1/3 rounded-lg" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-16 rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return null
  }

  const {
    total_appointments,
    high_risk_count,
    medium_risk_count,
    low_risk_count,
    average_risk_probability,
    items,
  } = data

  const avgRiskPct = Math.round(average_risk_probability * 100)
  const highRiskAppts = items?.filter((it) => it.risk_level === 'high') || []

  return (
    <div className="bg-brand-surface rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-teal-500/10 text-teal-600 flex items-center justify-center font-bold">
            <ClinicalIcon name="sparkles" size={18} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm sm:text-base font-bold text-brand-text">
                Appointment Attendance Risk Intelligence
              </h3>
              <Badge variant="teal" size="xs">AI Predictor</Badge>
            </div>
            <p className="text-[11px] text-brand-muted">
              Pre-consultation no-show probability and reminder recommendations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            as={Link}
            to="/doctor/appointments?risk_level=high"
            size="xs"
            variant="outline"
            className="text-xs font-semibold"
          >
            Filter High Risk ({high_risk_count})
          </Button>
          <button
            type="button"
            onClick={loadRiskSummary}
            className="p-1 rounded-lg border border-brand-border hover:bg-brand-ground text-brand-muted hover:text-brand-text cursor-pointer"
            title="Refresh attendance risk"
            aria-label="Refresh attendance risk"
          >
            <ClinicalIcon name="refresh" size={13} />
          </button>
        </div>
      </div>

      {/* Metric Pills */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* High Risk */}
        <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20">
          <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 block">
            High Risk (&ge;45%)
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-black text-rose-800">{high_risk_count}</span>
            <span className="text-[10px] text-rose-600 font-semibold">reminders advised</span>
          </div>
        </div>

        {/* Medium Risk */}
        <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20">
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 block">
            Medium Risk (25-45%)
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-black text-amber-800">{medium_risk_count}</span>
            <span className="text-[10px] text-amber-600 font-semibold">standard notice</span>
          </div>
        </div>

        {/* Low Risk */}
        <div className="p-3 rounded-2xl bg-teal-500/10 border border-teal-500/20">
          <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 block">
            Low Risk (&lt;25%)
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-black text-teal-800">{low_risk_count}</span>
            <span className="text-[10px] text-teal-600 font-semibold">on track</span>
          </div>
        </div>

        {/* Average Risk Rate */}
        <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border">
          <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted block">
            Average Absence Probability
          </span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-black text-brand-text">{avgRiskPct}%</span>
            <span className="text-[10px] text-brand-muted font-medium">across {total_appointments} visits</span>
          </div>
        </div>
      </div>

      {/* Action Recommendation Banner if High Risk Exists */}
      {high_risk_count > 0 && highRiskAppts.length > 0 && (
        <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200/80 flex items-center justify-between gap-3 text-xs text-amber-900">
          <div className="flex items-center gap-2">
            <ClinicalIcon name="sparkles" size={16} className="text-amber-600 shrink-0" />
            <span>
              <strong>Smart Action:</strong> {high_risk_count} upcoming consultation(s) have elevated absence likelihood. Review and dispatch reminders in the appointments tab.
            </span>
          </div>
          <Button
            as={Link}
            to="/doctor/appointments"
            size="xs"
            variant="outline"
            className="shrink-0 border-amber-300 bg-white hover:bg-amber-100/50 text-amber-900 font-bold"
          >
            Review Appointments &rarr;
          </Button>
        </div>
      )}
    </div>
  )
}

