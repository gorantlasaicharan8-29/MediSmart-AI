import React, { useState } from 'react'
import { Badge, Button, ClinicalIcon, EmptyState, Modal, ModalHeader, ModalBody, ModalFooter, Skeleton } from '../ui'

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
}) {
  const [activeDetailsAppt, setActiveDetailsAppt] = useState(null)

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
              ? `No ${statusFilter.replace('_', ' ')} appointments found for this date.`
              : 'There are no patient appointments scheduled for this date.'
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
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border/60">
              {appointments.map((appt) => {
                const patName = appt.patient?.full_name || 'Patient'
                const patPhone = appt.patient?.phone || 'No phone recorded'
                const timeDisplay = formatSlotTime(appt.appointment_time)

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
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setActiveDetailsAppt(appt)}
                        className="text-xs font-semibold text-brand-primary hover:text-brand-deep"
                      >
                        View Details
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Appointment Detail Modal */}
      {activeDetailsAppt && (
        <Modal
          isOpen={Boolean(activeDetailsAppt)}
          onClose={() => setActiveDetailsAppt(null)}
          title="Consultation Details"
          size="md"
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
            <div className="space-y-2">
              <label className="text-xs font-bold text-brand-text uppercase tracking-wider block">
                Patient Information
              </label>
              <div className="p-3.5 rounded-2xl bg-brand-surface border border-brand-border space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-brand-muted">Name</span>
                  <span className="font-bold text-brand-text">
                    {activeDetailsAppt.patient?.full_name || 'Patient'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-brand-muted">Phone Number</span>
                  <span className="font-medium text-brand-text">
                    {activeDetailsAppt.patient?.phone || 'Not provided'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-brand-muted">Email</span>
                  <span className="font-medium text-brand-text">
                    {activeDetailsAppt.patient?.email || 'Not provided'}
                  </span>
                </div>
              </div>
            </div>

            {/* Symptoms or Clinical Notes */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-brand-text uppercase tracking-wider block">
                Symptoms / Patient Notes
              </label>
              <div className="p-3.5 rounded-2xl bg-brand-ground border border-brand-border text-xs text-brand-text min-h-[60px]">
                {activeDetailsAppt.notes || (
                  <span className="text-brand-muted italic">No notes provided for this consultation.</span>
                )}
              </div>
            </div>
          </ModalBody>

          <ModalFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveDetailsAppt(null)}
              className="text-xs"
            >
              Close
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </div>
  )
}
