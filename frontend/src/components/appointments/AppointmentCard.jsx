import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import NoShowRiskBadge from './NoShowRiskBadge'
import { Badge, Button, ClinicalIcon } from '../ui'

// Helper to format slot time from "HH:MM" to "h:mm AM/PM"
function formatSlotTime(timeStr) {
  if (!timeStr) return ''
  const [hourStr, minStr] = timeStr.split(':')
  const hour = parseInt(hourStr, 10)
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${minStr} ${ampm}`
}

export default function AppointmentCard({
  appointment,
  onCancel,
  onCheckIn,
  isCancelling = false,
  isCheckingIn = false,
  priorStats = null,
  todayStr = '',
}) {
  const [copiedToken, setCopiedToken] = useState(false)

  const doctor = appointment.doctor || {}
  const doctorUser = doctor.user || {}
  const hospital = appointment.hospital || doctor.hospital || {}

  const isToday = Boolean(todayStr && appointment.appointment_date === todayStr)
  const isScheduled = appointment.status === 'scheduled'
  const isCheckedIn = appointment.status === 'checked_in'
  const isCompleted = appointment.status === 'completed'
  const isCancelled = appointment.status === 'cancelled'

  const handleCopyToken = () => {
    if (appointment.appointment_token) {
      navigator.clipboard.writeText(appointment.appointment_token)
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    }
  }

  // Render status badge using design system tokens
  const renderStatusBadge = () => {
    if (isScheduled) {
      return (
        <Badge variant="teal" size="sm" dot={true}>
          Scheduled
        </Badge>
      )
    }
    if (isCheckedIn) {
      return (
        <Badge variant="info" size="sm" dot={true}>
          Checked In / In Queue
        </Badge>
      )
    }
    if (isCompleted) {
      return (
        <Badge variant="success" size="sm" dot={true}>
          Completed
        </Badge>
      )
    }
    if (isCancelled) {
      return (
        <Badge variant="danger" size="sm" dot={true}>
          Cancelled
        </Badge>
      )
    }
    return (
      <Badge variant="neutral" size="sm">
        {appointment.status}
      </Badge>
    )
  }

  return (
    <div className="bg-brand-surface rounded-2xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs hover:shadow-clinical-sm transition-all duration-200 space-y-4">
      {/* Top Header: Reference Token + Status & ML Risk Badges */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-brand-border/70">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider">
            Token:
          </span>
          <div className="inline-flex items-center gap-1.5 bg-brand-ground px-2.5 py-1 rounded-xl border border-brand-border">
            <span className="font-mono text-xs sm:text-sm font-extrabold text-brand-deep tracking-wider">
              {appointment.appointment_token}
            </span>
            <button
              type="button"
              onClick={handleCopyToken}
              className="p-1 rounded text-brand-muted hover:text-brand-text hover:bg-stone-200 transition-colors cursor-pointer"
              title="Copy appointment token"
              aria-label="Copy token"
            >
              <ClinicalIcon
                name={copiedToken ? 'check' : 'copy'}
                size={12}
                ariaHidden="true"
              />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {renderStatusBadge()}
          <NoShowRiskBadge appointment={appointment} priorStats={priorStats} />
        </div>
      </div>

      {/* Main Grid: Specialist Details & Appointment Timing */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Doctor & Facility */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider block">
            Specialist & Facility
          </span>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-mint text-brand-deep font-bold flex items-center justify-center text-sm border border-teal-200 shrink-0 select-none">
              {doctorUser.full_name ? doctorUser.full_name.replace('Dr. ', '').charAt(0) : 'D'}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-bold text-brand-text truncate">
                {doctorUser.full_name || 'Medical Specialist'}
              </h3>
              <p className="text-xs text-brand-primary font-medium truncate">
                {doctor.specialty || 'General Consultation'}
              </p>
            </div>
          </div>
          <p className="text-xs text-brand-muted flex items-center gap-1.5 pt-0.5">
            <ClinicalIcon name="hospital" size={13} className="text-brand-muted shrink-0" ariaHidden="true" />
            <span className="truncate">{hospital.name || 'Hospital Clinic'}</span>
            {hospital.city && <span>• {hospital.city}</span>}
          </p>
        </div>

        {/* Consultation Schedule Box */}
        <div className="bg-brand-ground p-3.5 rounded-xl border border-brand-border space-y-1.5">
          <span className="text-[10px] font-bold text-brand-muted uppercase tracking-wider block">
            Consultation Schedule
          </span>
          <div className="flex items-center gap-2 text-sm font-bold text-brand-text">
            <ClinicalIcon name="calendar" size={16} className="text-brand-primary shrink-0" ariaHidden="true" />
            <span>{appointment.appointment_date}</span>
            <span className="text-brand-muted font-normal">at</span>
            <span className="text-brand-primary">
              {formatSlotTime(appointment.appointment_time)}
            </span>
          </div>
          {typeof doctor.consultation_fee === 'number' && (
            <p className="text-xs text-brand-muted flex items-center justify-between pt-0.5">
              <span>Consultation Fee:</span>
              <span className="font-bold text-brand-text">
                ₹{doctor.consultation_fee.toFixed(0)}{' '}
                <span className="text-[10px] font-normal text-brand-muted">(Pay at counter)</span>
              </span>
            </p>
          )}
        </div>
      </div>

      {/* Patient Notes */}
      {appointment.notes && (
        <div className="text-xs bg-brand-ground p-3 rounded-xl border border-brand-border text-brand-muted">
          <span className="font-bold text-brand-text block mb-0.5">Patient Notes:</span>
          <p className="leading-relaxed">{appointment.notes}</p>
        </div>
      )}

      {/* Cancellation Reason if Cancelled */}
      {appointment.cancellation_reason && (
        <div className="text-xs bg-clinical-danger-bg p-3 rounded-xl border border-clinical-danger-border text-clinical-danger">
          <span className="font-bold block mb-0.5">Reason for Cancellation:</span>
          <p className="leading-relaxed">{appointment.cancellation_reason}</p>
        </div>
      )}

      {/* Action Footer */}
      {(isScheduled || isCheckedIn) && (
        <div className="pt-2 border-t border-brand-border/70 flex flex-wrap items-center justify-between gap-3">
          {/* Status info or notice */}
          <div className="text-xs text-brand-muted">
            {isScheduled && !isToday && (
              <span className="inline-flex items-center gap-1.5">
                <ClinicalIcon name="clock" size={12} ariaHidden="true" />
                Check-in opens on appointment day ({appointment.appointment_date})
              </span>
            )}
            {isScheduled && isToday && (
              <span className="inline-flex items-center gap-1.5 text-brand-primary font-semibold">
                <ClinicalIcon name="check-circle" size={12} ariaHidden="true" />
                Appointment is today — Clinic check-in is open!
              </span>
            )}
            {isCheckedIn && (
              <span className="inline-flex items-center gap-1.5 text-brand-primary font-semibold">
                <ClinicalIcon name="ticket" size={12} ariaHidden="true" />
                Live queue position assigned
              </span>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 ml-auto">
            {isScheduled && isToday && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => onCheckIn(appointment)}
                isLoading={isCheckingIn}
                className="text-xs font-bold gap-1.5"
              >
                <ClinicalIcon name="ticket" size={13} ariaHidden="true" />
                <span>Check In to Queue</span>
              </Button>
            )}

            {isCheckedIn && (
              <Button
                variant="outline"
                size="sm"
                as={Link}
                to="/queue"
                className="text-xs font-semibold gap-1.5"
              >
                <ClinicalIcon name="waiting-time" size={13} ariaHidden="true" />
                <span>Track Live Queue</span>
              </Button>
            )}

            {isScheduled && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onCancel(appointment)}
                disabled={isCancelling}
                className="text-xs font-semibold text-clinical-danger hover:bg-clinical-danger-bg hover:text-clinical-danger"
              >
                Cancel Appointment
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
