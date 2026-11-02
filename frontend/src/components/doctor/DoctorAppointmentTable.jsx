import React, { useState, useEffect } from 'react'
import { Badge, Button, ClinicalIcon, EmptyState, Modal, ModalHeader, ModalBody, ModalFooter, Skeleton } from '../ui'
import { getAppointmentNoShowRisk, sendAppointmentReminder } from '../../services/api'
import ConsultationRecordModal from './ConsultationRecordModal'

function formatSlotTime(timeStr) {
  if (!timeStr) return ''
  const parts = timeStr.split(':')
  const hour = parseInt(parts[0], 10)
  const minute = parts[1] || '00'
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${minute} ${ampm}`
}

function getStatusBadge(status) {
  switch (status) {
    case 'scheduled':
      return <Badge variant="teal">Scheduled</Badge>
    case 'in_progress':
      return <Badge variant="warning">In Consultation</Badge>
    case 'completed':
      return <Badge variant="success">Completed</Badge>
    case 'cancelled':
      return <Badge variant="danger">Cancelled</Badge>
    case 'no_show':
      return <Badge variant="neutral">No Show</Badge>
    default:
      return <Badge variant="neutral">{status}</Badge>
  }
}

export default function DoctorAppointmentTable({
  appointments = [],
  isLoading = false,
  error = null,
  onRetry = () => {},
  selectedDate,
  onDateChange,
  statusFilter,
  onStatusChange,
  riskFilter = 'all',
  onRiskChange,
}) {
  const [activeDetailsAppt, setActiveDetailsAppt] = useState(null)
  const [activeConsultationAppt, setActiveConsultationAppt] = useState(null)
  const [riskAssessment, setRiskAssessment] = useState(null)
  const [isLoadingRisk, setIsLoadingRisk] = useState(false)
  const [riskError, setRiskError] = useState(null)

  // Reminder trigger state
  const [isSendingReminder, setIsSendingReminder] = useState(false)
  const [reminderStatus, setReminderStatus] = useState(null)

  // Fetch detailed risk assessment whenever an appointment is opened in modal
  useEffect(() => {
    let isMounted = true
    if (!activeDetailsAppt?.id) {
      setRiskAssessment(null)
      setReminderStatus(null)
      return
    }

    // Only fetch for active scheduled or checked_in appointments
    if (!['scheduled', 'checked_in'].includes(activeDetailsAppt.status)) {
      setRiskAssessment(null)
      return
    }

    setIsLoadingRisk(true)
    setRiskError(null)
    setReminderStatus(null)

    getAppointmentNoShowRisk(activeDetailsAppt.id)
      .then((res) => {
        if (isMounted) setRiskAssessment(res)
      })
      .catch((err) => {
        if (isMounted) setRiskError(err.message || 'Unable to load risk assessment')
      })
      .finally(() => {
        if (isMounted) setIsLoadingRisk(false)
      })

    return () => {
      isMounted = false
    }
  }, [activeDetailsAppt?.id, activeDetailsAppt?.status])

  // Handle send smart reminder
  const handleSendReminder = async () => {
    if (!activeDetailsAppt?.id || isSendingReminder) return
    setIsSendingReminder(true)
    setReminderStatus(null)
    try {
      const res = await sendAppointmentReminder(activeDetailsAppt.id)
      setReminderStatus({
        type: res.is_duplicate ? 'warning' : 'success',
        message: res.is_duplicate
          ? 'Notice: A reminder was already dispatched to this patient today.'
          : 'Smart reminder successfully dispatched to patient notifications!',
      })
    } catch (err) {
      setReminderStatus({
        type: 'danger',
        message: err.message || 'Failed to dispatch appointment reminder.',
      })
    } finally {
      setIsSendingReminder(false)
    }
  }

  return (
    <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs space-y-5">
      {/* Table Header & Filters */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base sm:text-lg font-bold text-brand-text">
            Consultation Schedule
          </h3>
          <p className="text-xs text-brand-muted">
            Manage your booked patient consultations and clinical records
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Date Selector */}
          {onDateChange && (
            <div className="flex items-center gap-1.5 bg-brand-ground p-1 rounded-xl border border-brand-border">
              <ClinicalIcon name="calendar" size={14} className="text-brand-muted ml-2" />
              <input
                type="date"
                value={selectedDate || ''}
                onChange={(e) => onDateChange(e.target.value)}
                className="text-xs bg-transparent border-0 font-semibold text-brand-text focus:outline-none pr-2 py-0.5"
                aria-label="Filter appointments by date"
              />
            </div>
          )}

          {/* Status Filter */}
          {onStatusChange && (
            <select
              value={statusFilter || 'all'}
              onChange={(e) => onStatusChange(e.target.value)}
              className="text-xs bg-brand-ground border border-brand-border rounded-xl px-3 py-1.5 font-semibold text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer"
              aria-label="Filter appointments by status"
            >
              <option value="all">All Statuses</option>
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">In Consultation</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          )}

          {/* Risk Level Filter (Phase 9.3) */}
          {onRiskChange && (
            <select
              value={riskFilter || 'all'}
              onChange={(e) => onRiskChange(e.target.value)}
              className="text-xs bg-brand-ground border border-brand-border rounded-xl px-3 py-1.5 font-semibold text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer"
              aria-label="Filter appointments by no-show risk"
            >
              <option value="all">All Risk Tiers</option>
              <option value="high">High Risk (&ge;45%)</option>
              <option value="medium">Medium Risk (25-45%)</option>
              <option value="low">Low Risk (&lt;25%)</option>
            </select>
          )}

          {/* Refresh Action */}
          <button
            type="button"
            onClick={onRetry}
            disabled={isLoading}
            className="p-1.5 rounded-xl border border-brand-border hover:bg-brand-ground text-brand-muted hover:text-brand-text transition-colors cursor-pointer"
            title="Refresh appointments list"
            aria-label="Refresh appointments list"
          >
            <ClinicalIcon name="refresh" size={16} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-3 py-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center justify-between p-3.5 rounded-2xl bg-brand-ground border border-brand-border animate-pulse">
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-1/4 rounded-md" />
                <Skeleton className="h-3 w-1/2 rounded-md" />
              </div>
              <Skeleton className="h-7 w-20 rounded-xl" />
            </div>
          ))}
        </div>
      )}

      {/* Error Banner with Retry */}
      {!isLoading && error && (
        <div className="p-4 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={18} className="shrink-0" />
            <span>{error}</span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="shrink-0 text-xs border-clinical-danger/30 hover:bg-clinical-danger/10 text-clinical-danger"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && appointments.length === 0 && (
        <EmptyState
          icon="calendar"
          title="No Appointments Found"
          description={
            statusFilter && statusFilter !== 'all'
              ? `No ${statusFilter.replace('_', ' ')} appointments found for this filter.`
              : 'There are no patient appointments scheduled matching your selection.'
          }
          className="py-10"
        />
      )}

      {/* Responsive Table */}
      {!isLoading && !error && appointments.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-brand-border">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-brand-ground/80 border-b border-brand-border text-brand-muted uppercase tracking-wider font-bold text-[10px]">
                <th className="py-3 px-4">Time</th>
                <th className="py-3 px-4">Patient</th>
                <th className="py-3 px-4">Reference</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">AI Attendance Risk</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border/60">
              {appointments.map((appt) => {
                const patName = appt.patient?.full_name || 'Patient'
                const patPhone = appt.patient?.phone || 'No phone recorded'
                const timeDisplay = formatSlotTime(appt.appointment_time)

                // Lead time heuristic for quick badge before modal click
                const isScheduled = ['scheduled', 'checked_in'].includes(appt.status)

                return (
                  <tr
                    key={appt.id}
                    className="hover:bg-brand-ground/40 transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-bold text-brand-text whitespace-nowrap">
                      {timeDisplay}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-brand-mint text-brand-deep font-bold flex items-center justify-center text-xs shrink-0">
                          {patName.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-brand-text truncate">{patName}</p>
                          <p className="text-[10px] text-brand-muted truncate">{patPhone}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-semibold text-brand-muted whitespace-nowrap">
                      {appt.appointment_token}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {getStatusBadge(appt.status)}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {isScheduled ? (
                        <button
                          type="button"
                          onClick={() => setActiveDetailsAppt(appt)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-teal-50 text-teal-800 border border-teal-200/80 hover:bg-teal-100 transition-colors cursor-pointer"
                          title="Click to view full no-show risk assessment and smart reminders"
                        >
                          <ClinicalIcon name="sparkles" size={11} className="text-teal-600" />
                          <span>Check AI Risk</span>
                        </button>
                      ) : (
                        <span className="text-[11px] text-brand-muted italic">Concluded</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          type="button"
                          variant={appt.status === 'completed' ? 'secondary' : 'primary'}
                          size="sm"
                          onClick={() => setActiveConsultationAppt(appt)}
                          className="text-xs font-semibold cursor-pointer"
                          title={appt.status === 'completed' ? 'View or edit EHR clinical notes and prescriptions' : 'Document clinical consultation, diagnoses, and prescriptions'}
                        >
                          <ClinicalIcon name="notes" size={12} className="mr-1" />
                          {appt.status === 'completed' ? 'EHR Record' : 'Document EHR'}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setActiveDetailsAppt(appt)}
                          className="text-xs font-semibold text-brand-primary hover:text-brand-deep cursor-pointer"
                        >
                          Details
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Appointment Detail & Attendance Risk Modal */}
      {activeDetailsAppt && (
        <Modal
          isOpen={Boolean(activeDetailsAppt)}
          onClose={() => setActiveDetailsAppt(null)}
          title="Consultation Details & AI Attendance Risk"
          size="lg"
        >
          <ModalHeader onClose={() => setActiveDetailsAppt(null)}>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-brand-text">
                Appointment Details
              </span>
              {getStatusBadge(activeDetailsAppt.status)}
            </div>
          </ModalHeader>

          <ModalBody className="space-y-4">
            {/* Reference & Time */}
            <div className="p-3.5 rounded-2xl bg-brand-ground border border-brand-border flex items-center justify-between">
              <div>
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Token</span>
                <span className="font-mono font-bold text-brand-text text-sm">
                  {activeDetailsAppt.appointment_token}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Date & Time</span>
                <span className="font-bold text-brand-text text-sm">
                  {activeDetailsAppt.appointment_date} at {formatSlotTime(activeDetailsAppt.appointment_time)}
                </span>
              </div>
            </div>

            {/* Patient Info */}
            <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-2">
              <span className="text-[10px] uppercase font-bold text-brand-muted block">
                Patient Contact
              </span>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-1">
                <span className="font-bold text-brand-text">
                  {activeDetailsAppt.patient?.full_name || 'Patient'}
                </span>
                <span className="text-brand-muted">
                  Phone: {activeDetailsAppt.patient?.phone || 'Not recorded'}
                </span>
                <span className="text-brand-muted">
                  Email: {activeDetailsAppt.patient?.email || 'Not recorded'}
                </span>
              </div>
            </div>

            {/* AI Attendance Risk Assessment (Phase 9.3) */}
            {['scheduled', 'checked_in'].includes(activeDetailsAppt.status) && (
              <div className="p-4 rounded-2xl bg-brand-ground/60 border border-brand-border space-y-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-teal-500/15 text-teal-600 flex items-center justify-center font-bold">
                      <ClinicalIcon name="sparkles" size={15} />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-brand-text">
                        AI Appointment No-Show Prediction
                      </h4>
                      <p className="text-[10px] text-brand-muted">
                        Evaluated via Logistic Regression (calibrated for clinical decision support)
                      </p>
                    </div>
                  </div>

                  {riskAssessment && (
                    <Badge
                      variant={
                        riskAssessment.risk_level === 'high'
                          ? 'danger'
                          : riskAssessment.risk_level === 'medium'
                          ? 'warning'
                          : 'teal'
                      }
                      size="sm"
                    >
                      {riskAssessment.risk_display_label} ({Math.round(riskAssessment.no_show_probability * 100)}%)
                    </Badge>
                  )}
                </div>

                {isLoadingRisk && (
                  <div className="py-4 space-y-2">
                    <Skeleton className="h-4 w-1/3 rounded-md" />
                    <Skeleton className="h-3 w-3/4 rounded-md" />
                  </div>
                )}

                {!isLoadingRisk && riskError && (
                  <p className="text-xs text-clinical-danger">{riskError}</p>
                )}

                {!isLoadingRisk && riskAssessment && (
                  <div className="space-y-3 text-xs">
                    {/* Gauge Bar */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-[11px]">
                        <span className="text-brand-muted">Absence Probability:</span>
                        <span className="font-bold text-brand-text">
                          {Math.round(riskAssessment.no_show_probability * 100)}%
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-brand-border/60 overflow-hidden">
                        <div
                          style={{ width: `${Math.round(riskAssessment.no_show_probability * 100)}%` }}
                          className={`h-full transition-all duration-500 rounded-full ${
                            riskAssessment.risk_level === 'high'
                              ? 'bg-rose-500'
                              : riskAssessment.risk_level === 'medium'
                              ? 'bg-amber-400'
                              : 'bg-teal-500'
                          }`}
                        />
                      </div>
                    </div>

                    {/* Contributing Risk Factors */}
                    {riskAssessment.risk_factors?.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted block">
                          Important Prediction Factors:
                        </span>
                        <ul className="space-y-1">
                          {riskAssessment.risk_factors.map((factor, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-[11px] text-brand-text">
                              <span
                                className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${
                                  factor.impact === 'increases_risk'
                                    ? 'bg-rose-500'
                                    : factor.impact === 'decreases_risk'
                                    ? 'bg-teal-500'
                                    : 'bg-slate-400'
                                }`}
                              />
                              <span>{factor.description}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Suggested Follow-up Action */}
                    <div className="p-3 rounded-xl bg-brand-surface border border-brand-border space-y-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted block">
                        Suggested Follow-Up Action:
                      </span>
                      <p className="text-xs text-brand-text leading-relaxed">
                        {riskAssessment.suggested_action}
                      </p>

                      {/* Smart Reminder Dispatch Action */}
                      {riskAssessment.reminder_recommended && (
                        <div className="pt-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="primary"
                            onClick={handleSendReminder}
                            disabled={isSendingReminder}
                            className="text-xs font-bold cursor-pointer"
                          >
                            <ClinicalIcon name="sparkles" size={13} className="mr-1.5" />
                            {isSendingReminder ? 'Dispatching Reminder...' : 'Send Smart Reminder to Patient'}
                          </Button>
                        </div>
                      )}

                      {/* Reminder feedback toast */}
                      {reminderStatus && (
                        <div
                          className={`p-2.5 rounded-xl text-xs font-semibold ${
                            reminderStatus.type === 'success'
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : reminderStatus.type === 'warning'
                              ? 'bg-amber-50 text-amber-800 border border-amber-200'
                              : 'bg-rose-50 text-rose-800 border border-rose-200'
                          }`}
                        >
                          {reminderStatus.message}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Symptoms or Notes */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-muted block">
                Symptoms / Patient Notes
              </span>
              <div className="p-3 rounded-2xl bg-brand-ground border border-brand-border text-xs text-brand-text min-h-[50px]">
                {activeDetailsAppt.notes || (
                  <span className="text-brand-muted italic">No notes provided for this consultation.</span>
                )}
              </div>
            </div>
          </ModalBody>

          <ModalFooter>
            <div className="w-full flex items-center justify-between gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  const appt = activeDetailsAppt
                  setActiveDetailsAppt(null)
                  setActiveConsultationAppt(appt)
                }}
                className="text-xs cursor-pointer font-bold"
              >
                <ClinicalIcon name="notes" size={13} className="mr-1.5" />
                {activeDetailsAppt.status === 'completed' ? 'Open EHR Record' : 'Document EHR Consultation'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveDetailsAppt(null)}
                className="text-xs cursor-pointer"
              >
                Close
              </Button>
            </div>
          </ModalFooter>
        </Modal>
      )}

      {/* Clinical Consultation & EHR Record Modal (Phase 10) */}
      {activeConsultationAppt && (
        <ConsultationRecordModal
          appointment={activeConsultationAppt}
          isOpen={Boolean(activeConsultationAppt)}
          onClose={() => setActiveConsultationAppt(null)}
          onSaved={() => {
            if (onRetry) onRetry()
            setActiveConsultationAppt(null)
          }}
        />
      )}
    </div>
  )
}
