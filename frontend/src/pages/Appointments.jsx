import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import AppointmentCard from '../components/appointments/AppointmentCard'
import { cancelAppointment, getMyAppointments } from '../services/api'

export default function Appointments() {
  const [appointments, setAppointments] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [cancellingId, setCancellingId] = useState(null)
  const [actionNotice, setActionNotice] = useState(null)

  const [reloadKey, setReloadKey] = useState(0)
  const refreshAppointments = () => {
    setIsLoading(true)
    setReloadKey((k) => k + 1)
  }

  useEffect(() => {
    let ignore = false

    const fetchAppointments = async () => {
      try {
        const params = { page: 1, page_size: 50 }
        if (statusFilter) {
          params.status = statusFilter
        }
        const data = await getMyAppointments(params)
        if (!ignore) {
          setAppointments(data.items || [])
          setTotal(data.total || 0)
          setError(null)
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || 'Failed to load appointments')
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    fetchAppointments()
    return () => {
      ignore = true
    }
  }, [statusFilter, reloadKey])

  const handleCancelAppointment = async (appointmentId, reason) => {
    setCancellingId(appointmentId)
    setError(null)
    setActionNotice(null)
    try {
      await cancelAppointment(appointmentId, reason)
      setActionNotice('Appointment cancelled successfully. The slot has been released for other patients.')
      refreshAppointments()
    } catch (err) {
      setError(err.message || 'Failed to cancel appointment')
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-teal-50 text-teal-800 border border-teal-200 mb-2">
            <span>📅</span> Patient Appointments Dashboard
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            My Consultation Appointments
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Track your upcoming consultations, view unique tracking reference tokens, and manage appointment bookings.
          </p>
        </div>

        <Link
          to="/doctors"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 shadow-sm transition-all shrink-0"
        >
          <span>+</span> Book New Consultation
        </Link>
      </div>

      {/* Status Notice */}
      {actionNotice && (
        <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center justify-between">
          <span>✓ {actionNotice}</span>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="text-emerald-700 hover:text-emerald-900 text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center justify-between">
          <span>⚠️ {error}</span>
          <button
            type="button"
            onClick={refreshAppointments}
            className="underline font-bold"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setStatusFilter('')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            statusFilter === ''
              ? 'bg-teal-600 text-white'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          All Appointments ({total})
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('scheduled')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            statusFilter === 'scheduled'
              ? 'bg-teal-600 text-white'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Upcoming / Scheduled
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('cancelled')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            statusFilter === 'cancelled'
              ? 'bg-teal-600 text-white'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
          }`}
        >
          Cancelled
        </button>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-white rounded-2xl border border-slate-200 p-6 space-y-3 animate-pulse"
            >
              <div className="h-4 bg-slate-200 rounded w-1/4"></div>
              <div className="h-5 bg-slate-200 rounded w-1/2"></div>
              <div className="h-4 bg-slate-100 rounded w-3/4"></div>
            </div>
          ))}
        </div>
      ) : appointments.length === 0 ? (
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center space-y-4 shadow-sm max-w-md mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-2xl">
            📅
          </div>
          <h3 className="text-base font-bold text-slate-900">No Appointments Found</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            {statusFilter
              ? `You don't have any appointments with status '${statusFilter}'.`
              : "You haven't scheduled any doctor consultations yet. Browse specialists across affiliated hospitals to book your first appointment."}
          </p>
          <Link
            to="/doctors"
            className="inline-block px-4 py-2 text-xs font-bold text-teal-700 bg-teal-50 hover:bg-teal-100 rounded-xl border border-teal-200 transition-colors"
          >
            Find a Doctor
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {appointments.map((appt) => (
            <AppointmentCard
              key={appt.id}
              appointment={appt}
              onCancel={handleCancelAppointment}
              isCancelling={cancellingId === appt.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
