import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { getMyDoctorProfile, getMyDoctorStats, getAppointments } from '../../services/api'
import DoctorStatCard from '../../components/doctor/DoctorStatCard'
import DoctorAppointmentTable from '../../components/doctor/DoctorAppointmentTable'
import DoctorQueuePanel from '../../components/doctor/DoctorQueuePanel'
import { Button, ClinicalIcon } from '../../components/ui'

function getTodayString() {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDisplayDate() {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function DoctorDashboard() {
  const { user } = useAuth()
  const [doctorProfile, setDoctorProfile] = useState(null)
  const [stats, setStats] = useState(null)
  const [isLoadingStats, setIsLoadingStats] = useState(true)
  const [statsError, setStatsError] = useState(null)

  // Appointments state for the table
  const [selectedDate, setSelectedDate] = useState(getTodayString())
  const [statusFilter, setStatusFilter] = useState('')
  const [appointments, setAppointments] = useState([])
  const [isLoadingAppointments, setIsLoadingAppointments] = useState(true)
  const [appointmentsError, setAppointmentsError] = useState(null)

  // 1. Fetch Doctor Profile & Stats
  const loadDoctorData = useCallback(async () => {
    setIsLoadingStats(true)
    setStatsError(null)
    try {
      const [profileData, statsData] = await Promise.all([
        getMyDoctorProfile().catch(() => null),
        getMyDoctorStats(),
      ])
      if (profileData) setDoctorProfile(profileData)
      setStats(statsData)
    } catch (err) {
      setStatsError(err.message || 'Failed to load doctor statistics')
    } finally {
      setIsLoadingStats(false)
    }
  }, [])

  // 2. Fetch Appointments for the selected date and status
  const loadAppointments = useCallback(async () => {
    setIsLoadingAppointments(true)
    setAppointmentsError(null)
    try {
      const params = { date: selectedDate }
      if (statusFilter) params.status = statusFilter
      const res = await getAppointments(params)
      setAppointments(res.items || res || [])
    } catch (err) {
      setAppointmentsError(err.message || 'Failed to load appointments')
    } finally {
      setIsLoadingAppointments(false)
    }
  }, [selectedDate, statusFilter])

  useEffect(() => {
    loadDoctorData()
  }, [loadDoctorData])

  useEffect(() => {
    loadAppointments()
  }, [loadAppointments])

  // Handle action in queue panel (e.g. called next, completed) -> refresh stats and table
  const handleQueueAction = () => {
    loadDoctorData()
    loadAppointments()
  }

  // Doctor name formatting
  const doctorName = doctorProfile?.user?.full_name || user?.full_name || 'Doctor'
  const formattedDoctorName = doctorName.startsWith('Dr.') ? doctorName : `Dr. ${doctorName}`

  // Next appointment summary display
  let nextApptDisplay = 'None Scheduled'
  let nextApptSub = 'All consultations up to date'
  if (stats?.next_appointment) {
    const na = stats.next_appointment
    const timeParts = na.appointment_time.split(':')
    const hr = parseInt(timeParts[0], 10)
    const ampm = hr >= 12 ? 'PM' : 'AM'
    const hr12 = hr % 12 || 12
    const formattedTime = `${hr12}:${timeParts[1]} ${ampm}`
    nextApptDisplay = formattedTime
    nextApptSub = `${na.patient_name} (${na.token_display || na.appointment_token})`
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fadeIn">
      {/* 1. Welcome Section */}
      <div className="bg-gradient-to-r from-teal-900 via-teal-800 to-teal-950 text-white rounded-3xl p-6 sm:p-8 shadow-clinical relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 rounded-full bg-teal-500/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-32 -mb-12 w-48 h-48 rounded-full bg-mint-400/10 blur-2xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full bg-teal-700/80 text-teal-100 text-[11px] font-bold tracking-wide uppercase border border-teal-600/50">
                Clinical Workspace
              </span>
              <span className="text-teal-200 text-xs font-semibold">
                &bull; {formatDisplayDate()}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Welcome back, {formattedDoctorName}!
            </h1>
            <p className="text-teal-100/90 text-xs sm:text-sm leading-relaxed">
              Here is your clinical summary for today. Manage your consultations, review waiting patients, and coordinate patient flow seamlessly.
            </p>
          </div>

          {/* Quick Action Shortcuts */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <Button
              as={Link}
              to="/doctor/appointments"
              variant="outline"
              size="sm"
              className="border-white/20 text-white hover:bg-white/10 hover:border-white/40 text-xs font-semibold backdrop-blur-xs"
            >
              <ClinicalIcon name="calendar" size={14} className="mr-1.5" />
              Appointments
            </Button>
            <Button
              as={Link}
              to="/doctor/queue"
              variant="secondary"
              size="sm"
              className="bg-brand-mint text-brand-deep hover:bg-teal-200 text-xs font-bold shadow-xs border-0"
            >
              <ClinicalIcon name="activity" size={14} className="mr-1.5" />
              Patient Queue
            </Button>
            <Button
              as={Link}
              to="/doctor/schedule"
              variant="outline"
              size="sm"
              className="border-white/20 text-white hover:bg-white/10 hover:border-white/40 text-xs font-semibold backdrop-blur-xs"
            >
              My Schedule
            </Button>
          </div>
        </div>
      </div>

      {/* 2. Four Live Summary Cards */}
      {statsError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-2xl flex items-center justify-between gap-3 text-xs text-red-800">
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert" size={16} className="text-red-600 shrink-0" />
            <span>{statsError}</span>
          </div>
          <Button size="xs" variant="outline" onClick={loadDoctorData}>
            Retry
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <DoctorStatCard
          title="Today's Appointments"
          value={stats?.today_appointments_count ?? 0}
          subtitle="Scheduled for today"
          icon="calendar"
          accentColor="teal"
          isLoading={isLoadingStats}
        />
        <DoctorStatCard
          title="Waiting Patients"
          value={stats?.waiting_patients_count ?? 0}
          subtitle="Ready in clinic queue"
          icon="users"
          accentColor="amber"
          isLoading={isLoadingStats}
        />
        <DoctorStatCard
          title="Completed Today"
          value={stats?.completed_consultations_count ?? 0}
          subtitle="Consultations concluded"
          icon="check"
          accentColor="emerald"
          isLoading={isLoadingStats}
        />
        <DoctorStatCard
          title="Next Appointment"
          value={nextApptDisplay}
          subtitle={nextApptSub}
          icon="activity"
          accentColor="cyan"
          isLoading={isLoadingStats}
        />
      </div>

      {/* 3. Two-Column Workspace Layout: Appointments (2/3) + Live Queue Panel (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8 items-start">
        {/* Left Column (2/3): Today's Appointments Table */}
        <div className="lg:col-span-2 space-y-4">
          <DoctorAppointmentTable
            appointments={appointments}
            isLoading={isLoadingAppointments}
            error={appointmentsError}
            onRetry={loadAppointments}
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            statusFilter={statusFilter}
            onStatusChange={setStatusFilter}
          />
        </div>

        {/* Right Column (1/3): Live Patient Queue Panel */}
        <div className="lg:col-span-1 space-y-4">
          <DoctorQueuePanel
            doctorId={doctorProfile?.id}
            onActionComplete={handleQueueAction}
          />
        </div>
      </div>
    </div>
  )
}
