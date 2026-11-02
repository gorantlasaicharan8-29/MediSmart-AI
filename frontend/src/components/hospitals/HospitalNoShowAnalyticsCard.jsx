import React, { useState, useEffect, useCallback } from 'react'
import { getHospitalNoShowAnalytics } from '../../services/api'
import { Badge, Button, ClinicalIcon, Skeleton } from '../ui'

export default function HospitalNoShowAnalyticsCard({ hospitalId = null, title = "Hospital No-Show & Attendance Intelligence" }) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadAnalytics = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await getHospitalNoShowAnalytics(hospitalId)
      setData(res)
    } catch (err) {
      setError(err.message || 'Unable to load hospital no-show analytics')
    } finally {
      setIsLoading(false)
    }
  }, [hospitalId])

  useEffect(() => {
    loadAnalytics()
  }, [loadAnalytics])

  if (isLoading) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 shadow-clinical-xs space-y-4 animate-pulse">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-1/3 rounded-lg" />
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-brand-surface rounded-3xl border border-clinical-danger-border/40 p-6 shadow-clinical-xs space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-clinical-danger font-bold text-sm">
            <ClinicalIcon name="alert-circle" size={18} />
            <span>Attendance Analytics Unavailable</span>
          </div>
          <Button size="xs" variant="outline" onClick={loadAnalytics}>
            Retry
          </Button>
        </div>
        <p className="text-xs text-brand-muted">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const {
    hospital_name,
    total_historical_appointments,
    attended_appointments,
    missed_appointments,
    historical_no_show_rate,
    scheduled_appointments_count,
    risk_distribution,
    specialty_trends,
  } = data

  const noShowPct = Math.round(historical_no_show_rate * 100)
  const attendanceRate = total_historical_appointments > 0
    ? Math.round((attended_appointments / total_historical_appointments) * 100)
    : 100

  return (
    <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 sm:p-7 shadow-clinical-xs space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-brand-primary" />
            <span className="text-[11px] font-bold text-brand-primary uppercase tracking-wider">
              {hospital_name} &bull; Clinical Operations
            </span>
          </div>
          <h3 className="text-lg sm:text-xl font-extrabold text-brand-text tracking-tight">
            {title}
          </h3>
          <p className="text-xs text-brand-muted mt-0.5">
            Logistic Regression analytics on patient attendance, scheduled risk distribution, and departmental trends.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Badge variant="teal" size="sm">
            Synthetic Model v1.0.0
          </Badge>
          <button
            type="button"
            onClick={loadAnalytics}
            className="p-1.5 rounded-xl border border-brand-border hover:bg-brand-ground text-brand-muted hover:text-brand-text transition-colors cursor-pointer"
            title="Refresh analytics"
            aria-label="Refresh attendance analytics"
          >
            <ClinicalIcon name="refresh" size={14} />
          </button>
        </div>
      </div>

      {/* Top 4 Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Total Historical */}
        <div className="p-4 rounded-2xl bg-brand-ground/70 border border-brand-border space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-muted block">
            Total Consultations
          </span>
          <div className="text-2xl font-black text-brand-text">
            {total_historical_appointments}
          </div>
          <span className="text-[10px] text-brand-muted">Recorded visits</span>
        </div>

        {/* Attended */}
        <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 block">
              Attended
            </span>
            <ClinicalIcon name="check" size={14} className="text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-emerald-800">
            {attended_appointments}
          </div>
          <span className="text-[10px] text-emerald-600/90 font-semibold">
            {attendanceRate}% completed rate
          </span>
        </div>

        {/* Missed / No-Show */}
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700 block">
              Missed Visits
            </span>
            <ClinicalIcon name="alert-circle" size={14} className="text-rose-600" />
          </div>
          <div className="text-2xl font-black text-rose-800">
            {missed_appointments}
          </div>
          <span className="text-[10px] text-rose-600/90 font-semibold">
            Unexcused absences
          </span>
        </div>

        {/* No-Show Rate */}
        <div className="p-4 rounded-2xl bg-brand-mint/50 border border-brand-primary/20 space-y-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-brand-deep block">
            No-Show Rate
          </span>
          <div className="text-2xl font-black text-brand-deep">
            {noShowPct}%
          </div>
          <span className="text-[10px] text-brand-muted">
            Baseline expected: ~23%
          </span>
        </div>
      </div>

      {/* Upcoming Scheduled Risk Distribution */}
      {risk_distribution && (
        <div className="p-5 rounded-2xl bg-brand-ground/50 border border-brand-border space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-text">
                Upcoming Consultations Attendance Risk ({scheduled_appointments_count} Scheduled)
              </h4>
              <p className="text-[11px] text-brand-muted">
                Pre-consultation classification: Low (&lt;25%), Medium (25-45%), High (&ge;45%)
              </p>
            </div>
            <span className="text-xs font-semibold text-brand-muted">
              {risk_distribution.high_risk_count} High Risk requires action
            </span>
          </div>

          {/* Tri-color Stacked Progress Bar */}
          <div className="w-full h-3.5 rounded-full bg-brand-border/60 overflow-hidden flex">
            <div
              style={{ width: `${risk_distribution.low_risk_percentage}%` }}
              className="bg-brand-primary h-full transition-all duration-500"
              title={`Low Risk: ${risk_distribution.low_risk_count} (${risk_distribution.low_risk_percentage}%)`}
            />
            <div
              style={{ width: `${risk_distribution.medium_risk_percentage}%` }}
              className="bg-amber-400 h-full transition-all duration-500"
              title={`Medium Risk: ${risk_distribution.medium_risk_count} (${risk_distribution.medium_risk_percentage}%)`}
            />
            <div
              style={{ width: `${risk_distribution.high_risk_percentage}%` }}
              className="bg-rose-500 h-full transition-all duration-500"
              title={`High Risk: ${risk_distribution.high_risk_count} (${risk_distribution.high_risk_percentage}%)`}
            />
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center justify-between text-xs pt-1 gap-2">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-brand-primary" />
              <span className="text-brand-text font-semibold">
                Low Risk: {risk_distribution.low_risk_count} ({risk_distribution.low_risk_percentage}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
              <span className="text-brand-text font-semibold">
                Medium Risk: {risk_distribution.medium_risk_count} ({risk_distribution.medium_risk_percentage}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <span className="text-rose-600 font-bold">
                High Risk: {risk_distribution.high_risk_count} ({risk_distribution.high_risk_percentage}%)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Specialty-Wise Breakdown Table */}
      {specialty_trends && specialty_trends.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-text">
            Specialty-Wise Attendance &amp; No-Show Trends
          </h4>
          <div className="overflow-x-auto rounded-2xl border border-brand-border">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-brand-ground/80 border-b border-brand-border text-brand-muted uppercase tracking-wider font-bold text-[10px]">
                  <th className="py-2.5 px-4">Specialty</th>
                  <th className="py-2.5 px-4">Total Consultations</th>
                  <th className="py-2.5 px-4">No-Show Count</th>
                  <th className="py-2.5 px-4">Absence Rate</th>
                  <th className="py-2.5 px-4 text-right">Attendance Pacing</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border/60">
                {specialty_trends.map((st) => {
                  const ratePct = Math.round(st.no_show_rate * 100)
                  return (
                    <tr key={st.specialty} className="hover:bg-brand-ground/40 transition-colors">
                      <td className="py-2.5 px-4 font-bold text-brand-text">
                        {st.specialty}
                      </td>
                      <td className="py-2.5 px-4 text-brand-muted">
                        {st.total_appointments}
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-rose-600">
                        {st.no_show_count}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className={`font-bold ${ratePct > 30 ? 'text-rose-600' : ratePct > 20 ? 'text-amber-600' : 'text-teal-700'}`}>
                          {ratePct}%
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="inline-block w-24 h-2 rounded-full bg-slate-200 overflow-hidden align-middle">
                          <div
                            style={{ width: `${100 - ratePct}%` }}
                            className="bg-brand-primary h-full rounded-full"
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Footer notice */}
      <p className="text-[11px] text-brand-muted border-t border-brand-border/70 pt-3">
        Attendance analytics are derived from historical consultation logs and evaluated through MediSmart's Logistic Regression pipeline. Reminders dispatched to high-risk appointments do not mutate clinical appointments.
      </p>
    </div>
  )
}

