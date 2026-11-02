import React, { useState, useEffect, useCallback } from 'react'
import { getDoctorQueueAnalytics } from '../../services/api'
import { Badge, Skeleton, ClinicalIcon } from '../ui'

function formatElapsed(minutes) {
  if (minutes == null) return '0 min'
  const totalSec = Math.floor(minutes * 60)
  const mins = Math.floor(totalSec / 60)
  const secs = totalSec % 60
  return `${mins}m ${secs.toString().padStart(2, '0')}s`
}

export default function DoctorQueueAnalyticsCard({ doctorId, reloadKey = 0 }) {
  const [analytics, setAnalytics] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadAnalytics = useCallback(async () => {
    if (!doctorId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await getDoctorQueueAnalytics(doctorId)
      setAnalytics(data)
    } catch (err) {
      setError(err.message || 'Unable to load queue analytics')
    } finally {
      setIsLoading(false)
    }
  }, [doctorId])

  useEffect(() => {
    loadAnalytics()
  }, [loadAnalytics, reloadKey])

  if (isLoading && !analytics) {
    return <Skeleton.Card lines={4} />
  }

  if (error && !analytics) {
    return null // Graceful failure: do not crash or clutter dashboard
  }

  const congestion = analytics?.queue_congestion_status || 'low'
  const congestionBadge = {
    low: { variant: 'teal', label: 'Optimal Flow' },
    moderate: { variant: 'warning', label: 'Moderate Pace' },
    high: { variant: 'warning', label: 'High Congestion' },
    congested: { variant: 'danger', label: 'Congested Queue' },
  }[congestion] || { variant: 'teal', label: 'Normal Flow' }

  return (
    <div className="rounded-3xl border border-stone-200 bg-white p-5 sm:p-6 shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-[#CCFBF1] text-[#0D9488] flex items-center justify-center font-bold shrink-0">
            <ClinicalIcon name="sparkles" size={16} ariaHidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-stone-900 tracking-tight">
              Intelligent Queue Flow Analytics
            </h3>
            <p className="text-[11px] text-stone-500">
              Real-time waiting-time prediction &amp; clinical pacing powered by XGBoost
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={congestionBadge.variant} size="sm">
            {congestionBadge.label}
          </Badge>
          <button
            type="button"
            onClick={loadAnalytics}
            className="p-1 rounded text-stone-400 hover:text-stone-700 transition-colors"
            title="Refresh queue analytics"
            aria-label="Refresh queue analytics"
          >
            <ClinicalIcon name="refresh" size={13} ariaHidden="true" />
          </button>
        </div>
      </div>

      {/* Grid of Key Queue Flow Indicators */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Metric 1: Currently Consulting */}
        <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/60 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block">
            In Consultation
          </span>
          <span className="font-mono text-lg font-extrabold text-stone-900 block truncate">
            {analytics?.currently_consulting_token || 'None Active'}
          </span>
          <span className="text-[10px] text-teal-700 font-semibold block">
            {analytics?.current_consultation_elapsed_minutes != null
              ? `Elapsed: ${formatElapsed(analytics.current_consultation_elapsed_minutes)}`
              : 'Room Ready'}
          </span>
        </div>

        {/* Metric 2: Patients Waiting */}
        <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/60 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block">
            Waiting in Queue
          </span>
          <span className="font-mono text-lg font-extrabold text-stone-900 block">
            {analytics?.waiting_patients_count ?? 0}
          </span>
          <span className="text-[10px] text-stone-500 font-medium block">
            Ready to call
          </span>
        </div>

        {/* Metric 3: Doctor's Historical Avg Duration */}
        <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/60 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block">
            Avg Consultation
          </span>
          <span className="font-mono text-lg font-extrabold text-stone-900 block">
            {analytics?.average_consultation_duration_minutes ?? 15.0}m
          </span>
          <span className="text-[10px] text-stone-500 font-medium block">
            Doctor pacing baseline
          </span>
        </div>

        {/* Metric 4: Est. Clearing Time */}
        <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/60 space-y-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block">
            Queue Clearing Time
          </span>
          <span className="font-mono text-lg font-extrabold text-[#0D9488] block">
            ~{analytics?.estimated_clearing_time_minutes ?? 0}m
          </span>
          <span className="text-[10px] text-stone-500 font-medium block">
            For {analytics?.waiting_patients_count ?? 0} patient(s)
          </span>
        </div>
      </div>

      {/* Analytics Summary Banner */}
      {analytics?.analytics_summary && (
        <div className="p-3 rounded-xl bg-teal-50/70 border border-teal-200/80 text-teal-900 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-medium">
            <ClinicalIcon name="activity" size={14} className="text-[#0D9488] shrink-0" ariaHidden="true" />
            <span>{analytics.analytics_summary}</span>
          </div>
          <span className="text-[10px] text-stone-500 shrink-0 font-medium">
            Completed today: <strong className="text-stone-800">{analytics.total_completed_today}</strong>
          </span>
        </div>
      )}

      {/* Waiting Queue Table Preview with predicted wait times */}
      {analytics?.waiting_queue && analytics.waiting_queue.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 block">
            Upcoming Waiting Patients (Predicted Wait Times)
          </span>
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {analytics.waiting_queue.slice(0, 5).map((item) => (
              <div
                key={item.queue_entry_id}
                className="flex items-center justify-between px-3 py-2 rounded-xl bg-stone-50 border border-stone-200/70 text-xs"
              >
                <div className="flex items-center gap-2.5">
                  <span className="w-5 h-5 rounded-md bg-stone-200 text-stone-700 font-bold text-[10px] flex items-center justify-center">
                    #{item.position}
                  </span>
                  <span className="font-mono font-bold text-stone-900">
                    {item.token_display}
                  </span>
                  <span className="text-stone-600 truncate max-w-[140px]">
                    {item.patient_name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-stone-500 text-[11px]">
                    Est. Wait:
                  </span>
                  <span className="font-mono font-bold text-[#0D9488] text-[11px] px-2 py-0.5 rounded-md bg-teal-50 border border-teal-200">
                    ~{item.predicted_wait_minutes} mins
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

