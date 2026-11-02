import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getAppointments } from '../../services/api'
import DoctorAppointmentTable from '../../components/doctor/DoctorAppointmentTable'
import { Button, ClinicalIcon } from '../../components/ui'

function getTodayString() {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export default function DoctorAppointments() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialRiskFilter = searchParams.get('risk_level') || 'all'

  const [selectedDate, setSelectedDate] = useState(getTodayString())
  const [statusFilter, setStatusFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState(initialRiskFilter)
  const [searchQuery, setSearchQuery] = useState('')
  const [appointments, setAppointments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchAppointments = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params = {}
      if (selectedDate) params.date = selectedDate
      if (statusFilter) params.status = statusFilter
      const res = await getAppointments(params)
      setAppointments(res.items || res || [])
    } catch (err) {
      setError(err.message || 'Failed to load doctor appointments')
    } finally {
      setIsLoading(false)
    }
  }, [selectedDate, statusFilter])

  useEffect(() => {
    fetchAppointments()
  }, [fetchAppointments])

  // Client-side search and risk filtering
  const filteredAppointments = appointments.filter((appt) => {
    // 1. Text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const patientName = appt.patient?.full_name?.toLowerCase() || ''
      const token = appt.appointment_token?.toLowerCase() || ''
      if (!patientName.includes(q) && !token.includes(q)) return false
    }

    // 2. Risk filter heuristic (if scheduled)
    if (riskFilter && riskFilter !== 'all') {
      const isSched = ['scheduled', 'checked_in'].includes(appt.status)
      if (!isSched) return false

      const apptDate = new Date(appt.appointment_date)
      const createdDate = new Date(appt.created_at || appt.appointment_date)
      const leadTime = Math.max(0, Math.round((apptDate.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24)))

      // Approximated tier based on lead time and notes for client list filter
      let approxTier = 'low'
      if (leadTime > 7) {
        approxTier = 'high'
      } else if (leadTime >= 3) {
        approxTier = 'medium'
      }

      if (approxTier !== riskFilter) return false
    }

    return true
  })

  const handleRiskChange = (newRisk) => {
    setRiskFilter(newRisk)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newRisk && newRisk !== 'all') {
        next.set('risk_level', newRisk)
      } else {
        next.delete('risk_level')
      }
      return next
    }, { replace: true })
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-brand-primary" />
            <span className="text-xs font-bold text-brand-primary uppercase tracking-wider">
              Clinical Consultations
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            My Appointments
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-0.5">
            View, search, and manage your booked patient consultations
          </p>
        </div>

        {/* Search input & Refresh */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Search patient or ref..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-brand-surface border border-brand-border rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text placeholder-brand-muted/70 w-52 sm:w-64"
            />
            <div className="absolute left-2.5 top-2 text-brand-muted">
              <ClinicalIcon name="search" size={12} />
            </div>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1.5 text-xs text-brand-muted hover:text-brand-text"
              >
                &times;
              </button>
            )}
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={fetchAppointments}
            className="text-xs"
          >
            <ClinicalIcon name="activity" size={14} className="mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Date Shortcuts Strip */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <Button
          size="xs"
          variant={selectedDate === getTodayString() ? 'primary' : 'outline'}
          onClick={() => setSelectedDate(getTodayString())}
          className="text-xs font-bold cursor-pointer"
        >
          Today
        </Button>
        <Button
          size="xs"
          variant={selectedDate === '' ? 'primary' : 'outline'}
          onClick={() => setSelectedDate('')}
          className="text-xs cursor-pointer"
        >
          All Dates
        </Button>
        <span className="text-xs text-brand-muted ml-2">
          {filteredAppointments.length} appointment{filteredAppointments.length === 1 ? '' : 's'} found
        </span>
      </div>

      {/* Main Appointment Table */}
      <DoctorAppointmentTable
        appointments={filteredAppointments}
        isLoading={isLoading}
        error={error}
        onRetry={fetchAppointments}
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        riskFilter={riskFilter}
        onRiskChange={handleRiskChange}
      />
    </div>
  )
}
