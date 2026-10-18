import React, { useState } from 'react'

export default function AppointmentCard({ appointment, onCancel, isCancelling }) {
  const [showConfirm, setShowConfirm] = useState(false)
  const [reason, setReason] = useState('')

  const doctor = appointment.doctor || {}
  const doctorUser = doctor.user || {}
  const hospital = appointment.hospital || doctor.hospital || {}

  const isScheduled = appointment.status === 'scheduled'

  const handleCancelSubmit = async (e) => {
    e.preventDefault()
    if (onCancel) {
      await onCancel(appointment.id, reason.trim())
      setShowConfirm(false)
    }
  }

  const renderStatusBadge = () => {
    switch (appointment.status) {
      case 'scheduled':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            Scheduled
          </span>
        )
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
            Cancelled
          </span>
        )
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
            Completed
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {appointment.status}
          </span>
        )
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-all space-y-4">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Token:</span>
          <span className="font-mono text-sm font-bold text-teal-800 bg-teal-50 px-2.5 py-0.5 rounded-lg border border-teal-100">
            {appointment.appointment_token}
          </span>
        </div>
        <div>{renderStatusBadge()}</div>
      </div>

      {/* Main Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Doctor & Hospital */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Specialist</span>
          <h3 className="text-base font-bold text-slate-900">
            {doctorUser.full_name || 'Medical Specialist'}
          </h3>
          <p className="text-xs text-teal-700 font-medium">{doctor.specialty || 'General Consultation'}</p>
          <p className="text-xs text-slate-500 flex items-center gap-1 pt-1">
            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <span className="truncate">{hospital.name || 'Hospital'}</span>
            {hospital.city && <span>• {hospital.city}</span>}
          </p>
        </div>

        {/* Schedule & Time */}
        <div className="space-y-1.5 bg-slate-50/70 p-3.5 rounded-xl border border-slate-100">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Consultation Schedule</span>
          <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <svg className="w-4 h-4 text-teal-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>{appointment.appointment_date}</span>
            <span className="text-slate-400">at</span>
            <span className="text-teal-700">{appointment.appointment_time}</span>
          </div>
          {doctor.consultation_fee && (
            <p className="text-xs text-slate-500">
              Fee: <span className="font-semibold text-slate-800">₹{doctor.consultation_fee.toFixed(0)}</span> (Pay at clinic counter)
            </p>
          )}
        </div>
      </div>

      {/* Patient Notes */}
      {appointment.notes && (
        <div className="text-xs bg-slate-50 p-3 rounded-xl border border-slate-100 text-slate-600">
          <span className="font-semibold text-slate-700 block mb-0.5">Notes:</span>
          {appointment.notes}
        </div>
      )}

      {/* Cancellation Reason if Cancelled */}
      {appointment.cancellation_reason && (
        <div className="text-xs bg-rose-50/80 p-3 rounded-xl border border-rose-100 text-rose-800">
          <span className="font-semibold text-rose-900 block mb-0.5">Cancellation Reason:</span>
          {appointment.cancellation_reason}
        </div>
      )}

      {/* Action Footer for Scheduled Appointments */}
      {isScheduled && (
        <div className="pt-2 flex items-center justify-end">
          {showConfirm ? (
            <form onSubmit={handleCancelSubmit} className="w-full bg-rose-50/80 p-4 rounded-xl border border-rose-200 space-y-3">
              <div className="text-xs text-rose-800 font-medium">
                Are you sure you want to cancel this appointment? The time slot will immediately be made available for other patients.
              </div>
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Optional reason for cancellation..."
                className="w-full px-3 py-1.5 rounded-lg border border-rose-300 bg-white text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-rose-400"
                maxLength={500}
              />
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowConfirm(false)}
                  className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800 font-semibold"
                >
                  Keep Appointment
                </button>
                <button
                  type="submit"
                  disabled={isCancelling}
                  className="px-4 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg shadow-sm transition-all"
                >
                  {isCancelling ? 'Cancelling...' : 'Confirm Cancellation'}
                </button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => setShowConfirm(true)}
              className="text-xs text-rose-600 hover:text-rose-700 font-semibold py-1.5 px-3 rounded-lg hover:bg-rose-50 transition-colors"
            >
              Cancel Appointment
            </button>
          )}
        </div>
      )}
    </div>
  )
}
