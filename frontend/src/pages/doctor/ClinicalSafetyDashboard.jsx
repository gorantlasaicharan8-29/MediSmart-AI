import React, { useState, useEffect, useCallback } from 'react'
import {
  getCDSSDashboardMetrics,
  getCDSSContraindications,
} from '../../services/api'
import { Badge, Button, ClinicalIcon, EmptyState, SkeletonCard } from '../../components/ui'

function formatDate(dateStr) {
  if (!dateStr) return 'N/A'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

export default function ClinicalSafetyDashboard() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [contraindications, setContraindications] = useState([])
  const [activeTab, setActiveTab] = useState('audit-trail') // 'audit-trail' | 'contraindications' | 'guidelines' | 'feedback'

  // Filter states
  const [dateRange, setDateRange] = useState('30d') // 'today' | '7d' | '30d' | 'all'
  const [severityFilter, setSeverityFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')

  const fetchDashboardData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (severityFilter) params.severity = severityFilter
      if (categoryFilter) params.warning_category = categoryFilter

      const now = new Date()
      if (dateRange === 'today') {
        params.start_date = now.toISOString().split('T')[0]
        params.end_date = now.toISOString().split('T')[0]
      } else if (dateRange === '7d') {
        const past = new Date(now)
        past.setDate(past.getDate() - 7)
        params.start_date = past.toISOString().split('T')[0]
      } else if (dateRange === '30d') {
        const past = new Date(now)
        past.setDate(past.getDate() - 30)
        params.start_date = past.toISOString().split('T')[0]
      }

      const [metricsData, ciData] = await Promise.all([
        getCDSSDashboardMetrics(params),
        getCDSSContraindications().catch(() => []),
      ])

      setMetrics(metricsData)
      setContraindications(ciData || [])
    } catch (err) {
      console.error('Failed to load CDSS safety dashboard:', err)
      setError(err.message || 'Failed to load clinical safety dashboard metrics')
    } finally {
      setLoading(false)
    }
  }, [dateRange, severityFilter, categoryFilter])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  const getSeverityBadge = (sev) => {
    const s = (sev || '').toUpperCase()
    if (s === 'CRITICAL') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
          CRITICAL
        </span>
      )
    }
    if (s === 'HIGH') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300">
          HIGH
        </span>
      )
    }
    if (s === 'MODERATE') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
          MODERATE
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
        INFORMATIONAL
      </span>
    )
  }

  const getActionBadge = (action) => {
    const a = (action || '').toUpperCase()
    if (a === 'ACKNOWLEDGED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
          ✓ Acknowledged
        </span>
      )
    }
    if (a === 'DISMISSED') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">
          ✕ Dismissed with Note
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
        ⚠ Unresolved
      </span>
    )
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl p-6 border border-brand-border shadow-xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-xl bg-teal-50 border border-teal-200 flex items-center justify-center text-teal-800">
                <ClinicalIcon name="shield-check" size={24} />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-xl sm:text-2xl font-bold text-brand-text tracking-tight">
                    CDSS Safety & Governance Dashboard
                  </h1>
                  {metrics?.knowledge_base_status && (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-teal-100 text-teal-800 border border-teal-300">
                      KB v{metrics.knowledge_base_status.version}
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                    Phase 11.3 Active
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-brand-muted">
                  Surveillance of drug interactions, absolute contraindications, guideline freshness, and clinician overrides.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDashboardData}
              disabled={loading}
              className="flex items-center gap-1.5 text-xs text-brand-text hover:bg-brand-ground"
            >
              <ClinicalIcon name="refresh" size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="mt-5 pt-4 border-t border-brand-border/70 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-brand-muted">Timeframe:</span>
            {[
              { id: 'today', label: 'Today' },
              { id: '7d', label: 'Last 7 Days' },
              { id: '30d', label: 'Last 30 Days' },
              { id: 'all', label: 'All Time' },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setDateRange(t.id)}
                className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                  dateRange === t.id
                    ? 'bg-teal-700 text-white shadow-xs'
                    : 'bg-brand-ground text-brand-muted hover:text-brand-text'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-2.5 py-1 rounded-lg border border-brand-border bg-white text-brand-text text-xs focus:ring-1 focus:ring-brand-accent focus:outline-none"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MODERATE">Moderate</option>
              <option value="INFORMATIONAL">Informational</option>
            </select>

            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-2.5 py-1 rounded-lg border border-brand-border bg-white text-brand-text text-xs focus:ring-1 focus:ring-brand-accent focus:outline-none"
            >
              <option value="">All Alert Categories</option>
              <option value="DRUG_INTERACTION">Drug Interactions</option>
              <option value="CONTRAINDICATION">Contraindications</option>
              <option value="ALLERGY_CONFLICT">Allergy Conflicts</option>
              <option value="MISSING_INSTRUCTIONS">Missing Instructions</option>
              <option value="DUPLICATE_THERAPY">Duplicate Therapy</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm flex items-start gap-2.5">
          <ClinicalIcon name="alert-triangle" size={18} className="shrink-0 mt-0.5 text-rose-600" />
          <div className="flex-1">
            <p className="font-semibold">Unable to load safety metrics</p>
            <p className="text-xs text-rose-700 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Top 5 Metric Stat Cards */}
      {loading && !metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonCard key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Card 1: Total Alerts */}
          <div className="bg-white rounded-2xl p-4 border border-brand-border shadow-xs hover:border-teal-300 transition-all">
            <div className="flex items-center justify-between text-xs text-brand-muted">
              <span className="font-medium">Total Safety Alerts</span>
              <ClinicalIcon name="bell" size={16} className="text-brand-muted" />
            </div>
            <div className="mt-2 text-2xl font-bold text-brand-text">
              {metrics?.total_alerts ?? 0}
            </div>
            <div className="mt-1 text-[11px] text-brand-muted flex items-center gap-1.5">
              <span className="text-rose-600 font-bold">{metrics?.critical_alerts ?? 0} Critical</span>
              <span>•</span>
              <span className="text-amber-600 font-bold">{metrics?.high_alerts ?? 0} High</span>
            </div>
          </div>

          {/* Card 2: Resolution Rate */}
          <div className="bg-white rounded-2xl p-4 border border-brand-border shadow-xs hover:border-teal-300 transition-all">
            <div className="flex items-center justify-between text-xs text-brand-muted">
              <span className="font-medium">Resolution Rate</span>
              <ClinicalIcon name="check-circle" size={16} className="text-emerald-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-emerald-700">
              {metrics?.resolution_rate_percent ?? 100}%
            </div>
            <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-emerald-600 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, metrics?.resolution_rate_percent ?? 100)}%` }}
              />
            </div>
          </div>

          {/* Card 3: Action Breakdown */}
          <div className="bg-white rounded-2xl p-4 border border-brand-border shadow-xs hover:border-teal-300 transition-all">
            <div className="flex items-center justify-between text-xs text-brand-muted">
              <span className="font-medium">Clinician Actions</span>
              <ClinicalIcon name="user-check" size={16} className="text-blue-600" />
            </div>
            <div className="mt-2 text-sm space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-emerald-700 font-medium">Acknowledged:</span>
                <span className="font-bold">{metrics?.acknowledged_count ?? 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-indigo-700 font-medium">Dismissed:</span>
                <span className="font-bold">{metrics?.dismissed_count ?? 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-rose-700 font-medium">Unresolved:</span>
                <span className="font-bold">{metrics?.unresolved_count ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Card 4: Overdue Guidelines */}
          <div className="bg-white rounded-2xl p-4 border border-brand-border shadow-xs hover:border-teal-300 transition-all">
            <div className="flex items-center justify-between text-xs text-brand-muted">
              <span className="font-medium">Overdue Guidelines</span>
              <ClinicalIcon
                name="alert-triangle"
                size={16}
                className={metrics?.overdue_guidelines_count > 0 ? 'text-amber-500' : 'text-slate-400'}
              />
            </div>
            <div className="mt-2 text-2xl font-bold">
              {metrics?.overdue_guidelines_count > 0 ? (
                <span className="text-amber-600">{metrics.overdue_guidelines_count}</span>
              ) : (
                <span className="text-emerald-700">0</span>
              )}
            </div>
            <div className="mt-1 text-[11px] text-brand-muted">
              {metrics?.overdue_guidelines_count > 0 ? (
                <span className="text-amber-600 font-semibold">Review Required</span>
              ) : (
                <span className="text-emerald-600 font-medium">All Guidelines Current</span>
              )}
            </div>
          </div>

          {/* Card 5: Clinician Feedback */}
          <div className="bg-white rounded-2xl p-4 border border-brand-border shadow-xs hover:border-teal-300 transition-all">
            <div className="flex items-center justify-between text-xs text-brand-muted">
              <span className="font-medium">Clinician Feedback</span>
              <ClinicalIcon name="message-square" size={16} className="text-teal-600" />
            </div>
            <div className="mt-2 text-2xl font-bold text-brand-text">
              {metrics?.clinician_feedback_stats?.total_submissions ?? 0}
            </div>
            <div className="mt-1 text-[11px] text-brand-muted">
              <span className="text-teal-700 font-semibold">
                {metrics?.clinician_feedback_stats?.pending_review ?? 0} Pending QA Review
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-brand-border overflow-x-auto pb-1 text-xs sm:text-sm font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab('audit-trail')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
            activeTab === 'audit-trail'
              ? 'border-teal-700 text-teal-900 font-bold'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          <ClinicalIcon name="clipboard-list" size={16} />
          Safety Events Audit Log (Zero PHI)
          <span className="px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-700 text-xs font-bold">
            {metrics?.recent_safety_events?.length ?? 0}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('contraindications')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
            activeTab === 'contraindications'
              ? 'border-teal-700 text-teal-900 font-bold'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          <ClinicalIcon name="alert-octagon" size={16} />
          Accredited Contraindications Catalog
          <span className="px-1.5 py-0.2 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-xs font-bold">
            {contraindications.length} Active Rules
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('guidelines')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
            activeTab === 'guidelines'
              ? 'border-teal-700 text-teal-900 font-bold'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          <ClinicalIcon name="file-text" size={16} />
          Guideline Governance & Freshness
          {metrics?.overdue_guidelines_count > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 text-xs font-bold">
              {metrics.overdue_guidelines_count} Overdue
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('feedback')}
          className={`px-4 py-2.5 border-b-2 transition-colors whitespace-nowrap flex items-center gap-2 ${
            activeTab === 'feedback'
              ? 'border-teal-700 text-teal-900 font-bold'
              : 'border-transparent text-brand-muted hover:text-brand-text'
          }`}
        >
          <ClinicalIcon name="message-circle" size={16} />
          Clinician Feedback & QA
        </button>
      </div>

      {/* Tab 1: Safety Events Audit Log */}
      {activeTab === 'audit-trail' && (
        <div className="bg-white rounded-2xl border border-brand-border shadow-xs overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-brand-border bg-slate-50/60 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-brand-text">Recent Clinical Safety Events</h2>
              <p className="text-xs text-brand-muted">
                Sanitized audit records of alerts triggered during clinical encounters. Zero PHI (no patient names or identifiers exposed).
              </p>
            </div>
          </div>

          {!metrics?.recent_safety_events || metrics.recent_safety_events.length === 0 ? (
            <div className="p-8">
              <EmptyState
                icon="shield-check"
                title="No safety events recorded"
                description="No safety alerts match the current filter criteria or have been triggered in this timeframe."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-brand-border bg-slate-50 text-brand-muted uppercase font-bold tracking-wider">
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Severity</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Rule Identifier</th>
                    <th className="py-3 px-4">Alert Summary</th>
                    <th className="py-3 px-4">Resolution Status</th>
                    <th className="py-3 px-4">Clinician Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-border text-brand-text">
                  {metrics.recent_safety_events.map((evt) => (
                    <tr key={evt.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-4 font-mono text-[11px] whitespace-nowrap text-brand-muted">
                        {formatDate(evt.created_at)}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        {getSeverityBadge(evt.warning_severity)}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap font-medium text-[11px]">
                        <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                          {evt.warning_category}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-teal-800 font-bold whitespace-nowrap">
                        {evt.rule_identifier}
                      </td>
                      <td className="py-3 px-4 max-w-sm">
                        <p className="line-clamp-2 text-brand-text font-medium leading-relaxed">
                          {evt.alert_summary}
                        </p>
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        {getActionBadge(evt.action_taken)}
                      </td>
                      <td className="py-3 px-4 max-w-xs text-brand-muted italic text-[11px]">
                        {evt.clinician_justification || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Absolute Contraindications Catalog */}
      {activeTab === 'contraindications' && (
        <div className="space-y-4">
          <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 sm:p-5 flex items-start gap-3 text-rose-900 text-xs sm:text-sm">
            <ClinicalIcon name="alert-octagon" size={24} className="text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-sm sm:text-base">Absolute Clinical Contraindications Engine</p>
              <p className="text-xs text-rose-800 mt-1 leading-relaxed">
                The CDSS cross-checks proposed medications against active patient diagnoses, chronic medical history, and clinical documentation.
                These rules represent established absolute contraindications based on FDA black-box warnings, KDIGO, GINA, and ADA clinical practice standards.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {contraindications.map((ci) => (
              <div
                key={ci.rule_id}
                className="bg-white rounded-2xl p-5 border border-brand-border shadow-xs hover:border-rose-300 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 px-2.5 py-1 rounded-lg border border-teal-200">
                      {ci.rule_id}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
                      ABSOLUTE CONTRAINDICATION
                    </span>
                  </div>

                  <h3 className="mt-3 font-bold text-base text-brand-text">
                    {ci.medication_name} in {ci.contraindicated_condition}
                  </h3>

                  <div className="mt-2.5 p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1.5">
                    <p className="text-slate-800 font-medium">
                      <span className="text-rose-700 font-bold">Clinical Hazard: </span>
                      {ci.clinical_risk}
                    </p>
                    <p className="text-emerald-800 font-medium">
                      <span className="font-bold">Mandated Action: </span>
                      {ci.recommended_action}
                    </p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-brand-border/70 flex items-center justify-between text-[11px] text-brand-muted">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-700">{ci.evidence_source}</span>
                    <span className="px-1.5 py-0.2 rounded-md bg-teal-50 text-teal-700 font-bold text-[10px]">
                      {ci.evidence_class}
                    </span>
                  </div>
                  {ci.evidence_url && (
                    <a
                      href={ci.evidence_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-700 hover:text-teal-900 font-bold underline inline-flex items-center gap-0.5"
                    >
                      Evidence Reference ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Clinical Guidelines Governance */}
      {activeTab === 'guidelines' && (
        <div className="bg-white rounded-2xl border border-brand-border shadow-xs overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-brand-border bg-slate-50/60 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-brand-text">Clinical Practice Guidelines Freshness</h2>
              <p className="text-xs text-brand-muted">
                Guidelines tracked by the CDSS knowledge base. Any guideline whose next review date has passed is automatically flagged as REVIEW_REQUIRED.
              </p>
            </div>
          </div>

          <div className="divide-y divide-brand-border">
            {metrics?.overdue_guidelines && metrics.overdue_guidelines.length > 0 ? (
              metrics.overdue_guidelines.map((g) => (
                <div key={g.guideline_id} className="p-5 hover:bg-slate-50/60 transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded-md border border-teal-200">
                        {g.guideline_id}
                      </span>
                      <h3 className="text-sm font-bold text-brand-text">{g.title}</h3>
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                        ⚠ Review Overdue ({Math.abs(g.days_until_review || 0)} days past due)
                      </span>
                    </div>
                    <span className="text-xs text-brand-muted">
                      Issuing Body: <strong className="text-brand-text">{g.issuing_authority}</strong>
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-brand-muted leading-relaxed">
                    {g.summary}
                  </p>

                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded-lg bg-teal-50 text-teal-800 font-semibold border border-teal-200">
                      First-line: {g.first_line_recommendation}
                    </span>
                    <span className="px-2 py-1 rounded-lg bg-slate-100 text-slate-700 font-medium">
                      Next Review Due: {g.next_review_date}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8">
                <EmptyState
                  icon="check-circle"
                  title="All Clinical Guidelines Current"
                  description="All active clinical guidelines in the knowledge base are within their validity review windows."
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Clinician Feedback & QA */}
      {activeTab === 'feedback' && (
        <div className="bg-white rounded-2xl border border-brand-border shadow-xs p-6 space-y-6">
          <div>
            <h2 className="text-base font-bold text-brand-text">Clinician Feedback & Quality Assurance</h2>
            <p className="text-xs text-brand-muted">
              Feedback submitted by clinicians during active consultations to report inaccurate interaction alerts, outdated guidelines, or suggested improvements.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs text-brand-muted font-medium">Total Feedback Reports</span>
              <p className="text-2xl font-bold text-brand-text mt-1">
                {metrics?.clinician_feedback_stats?.total_submissions ?? 0}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-teal-50 border border-teal-200">
              <span className="text-xs text-teal-800 font-medium">Pending Clinical Governance Review</span>
              <p className="text-2xl font-bold text-teal-900 mt-1">
                {metrics?.clinician_feedback_stats?.pending_review ?? 0}
              </p>
            </div>
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200">
              <span className="text-xs text-emerald-800 font-medium">Knowledge Base Policy</span>
              <p className="text-xs font-semibold text-emerald-900 mt-1">
                Dual Physician Sign-off Required Before Rule Activation
              </p>
            </div>
          </div>

          {metrics?.clinician_feedback_stats?.submissions_by_type && (
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-brand-muted mb-2">
                Submissions by Category
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Object.entries(metrics.clinician_feedback_stats.submissions_by_type).map(([cat, cnt]) => (
                  <div key={cat} className="p-3 rounded-lg border border-brand-border bg-white text-xs flex justify-between">
                    <span className="text-slate-700 font-medium">{cat}</span>
                    <span className="font-bold text-brand-text">{cnt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

