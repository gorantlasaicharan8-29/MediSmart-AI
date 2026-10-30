import React, { useState, useEffect, useCallback } from 'react'
import { getDoctorSlots, getAppointments } from '../../services/api'
import { Badge, Button, ClinicalIcon, Modal, ModalHeader, ModalBody, ModalFooter, Skeleton } from '../ui'

function formatSlotTime(timeStr) {
  if (!timeStr) return ''
  const parts = timeStr.split(':')
  const hour = parseInt(parts[0], 10)
  const minute = parts[1] || '00'
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${minute} ${ampm}`
}

function getClinicTodayStr() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(dateStr, days) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export default function DoctorScheduleCalendar({ doctorId, doctorProfile }) {
  const [selectedDate, setSelectedDate] = useState(getClinicTodayStr())
  const [slotsData, setSlotsData] = useState(null)
  const [dayAppointments, setDayAppointments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedApptModal, setSelectedApptModal] = useState(null)

  // Fetch slots and appointments for the selected date
  const loadSchedule = useCallback(async () => {
    if (!doctorId) {
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const [slotsRes, apptsRes] = await Promise.all([
        getDoctorSlots(doctorId, selectedDate).catch((err) => {
          // If past date, backend returns 400 with detail "Cannot query consultation slots for past dates"
          return { slots: [], is_working_day: true, error: err.message }
        }),
        getAppointments({ date: selectedDate }).catch(() => ({ items: [] })),
      ])

      setSlotsData(slotsRes)
      setDayAppointments(apptsRes.items || apptsRes || [])
    } catch (err) {
      setError(err.message || 'Failed to load doctor schedule')
    } finally {
      setIsLoading(false)
    }
  }, [doctorId, selectedDate])

  useEffect(() => {
    loadSchedule()
  }, [loadSchedule])

  // Map appointment times to appointment details
  const apptByTime = {}
  dayAppointments.forEach((appt) => {
    if (appt.appointment_time) {
      const timePrefix = appt.appointment_time.slice(0, 5)
      apptByTime[timePrefix] = appt
    }
  })

  // Date formatting helpers
  const dateObj = new Date(selectedDate)
  const dayOfWeek = dateObj.toLocaleDateString('en-US', { weekday: 'long' })
  const formattedDisplayDate = dateObj.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  // Working days of doctor
  const workingDays = doctorProfile?.available_days || ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
  const isDoctorWorkingDay = workingDays.includes(dayOfWeek)

  const morningSlots = (slotsData?.slots || []).filter((s) => {
    const hour = parseInt(s.time.split(':')[0], 10)
    return hour < 13
  })

  const afternoonSlots = (slotsData?.slots || []).filter((s) => {
    const hour = parseInt(s.time.split(':')[0], 10)
    return hour >= 13
  })

  // Navigate date
  const handlePrevDay = () => setSelectedDate((prev) => addDays(prev, -1))
  const handleNextDay = () => setSelectedDate((prev) => addDays(prev, 1))
  const handleSetToday = () => setSelectedDate(getClinicTodayStr())

  // Generate 7 days for weekly tabs
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const dStr = addDays(selectedDate, i - 3)
    const d = new Date(dStr)
    return {
      dateStr: dStr,
      dayName: d.toLocaleDateString('en-US', { weekday: 'short' }),
      dayNum: d.getDate(),
      isWorking: workingDays.includes(d.toLocaleDateString('en-US', { weekday: 'long' })),
      isCurrent: dStr === selectedDate,
    }
  })

  return (
    <div className="space-y-6">
      {/* Calendar Controls Card */}
      <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-brand-border/70">
          <div>
            <h2 className="text-lg sm:text-xl font-extrabold text-brand-text flex items-center gap-2">
              <ClinicalIcon name="calendar" size={20} className="text-brand-primary" />
              Doctor Consultation Schedule
            </h2>
            <p className="text-xs text-brand-muted mt-0.5">
              Review booked patient slots, clinic availability, and session capacity
            </p>
          </div>

          {/* Quick Date Switcher Controls */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center rounded-xl border border-brand-border bg-brand-ground p-1">
              <button
                type="button"
                onClick={handlePrevDay}
                aria-label="Previous Day"
                className="p-1.5 rounded-lg hover:bg-white text-brand-text transition-colors cursor-pointer"
              >
                &larr;
              </button>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
                className="bg-transparent text-xs font-bold text-brand-text px-2 py-1 focus:outline-none cursor-pointer"
              />
              <button
                type="button"
                onClick={handleNextDay}
                aria-label="Next Day"
                className="p-1.5 rounded-lg hover:bg-white text-brand-text transition-colors cursor-pointer"
              >
                &rarr;
              </button>
            </div>

            <Button
              size="sm"
              variant={selectedDate === getClinicTodayStr() ? 'primary' : 'outline'}
              onClick={handleSetToday}
              className="text-xs font-semibold"
            >
              Today
            </Button>

            <Button
              size="sm"
              variant="outline"
              onClick={loadSchedule}
              className="text-xs text-brand-muted hover:text-brand-text"
              aria-label="Refresh Schedule"
            >
              <ClinicalIcon name="activity" size={14} className="mr-1" />
              Refresh
            </Button>
          </div>
        </div>

        {/* 7-Day Quick Strip */}
        <div className="pt-4 flex items-center gap-2 overflow-x-auto pb-1">
          {weekDays.map((w) => (
            <button
              key={w.dateStr}
              type="button"
              onClick={() => setSelectedDate(w.dateStr)}
              className={`flex-1 min-w-[72px] p-2.5 rounded-2xl border text-center transition-all cursor-pointer ${
                w.isCurrent
                  ? 'bg-brand-primary text-white border-brand-primary shadow-xs font-bold scale-[1.02]'
                  : 'bg-brand-ground/60 border-brand-border hover:bg-white hover:border-brand-primary/40 text-brand-text'
              }`}
            >
              <span className={`text-[11px] block font-medium ${w.isCurrent ? 'text-teal-100' : 'text-brand-muted'}`}>
                {w.dayName}
              </span>
              <span className="text-base font-extrabold block my-0.5">
                {w.dayNum}
              </span>
              <span className={`text-[9px] uppercase tracking-wider block font-bold ${
                w.isCurrent
                  ? 'text-mint-200'
                  : w.isWorking
                  ? 'text-teal-700'
                  : 'text-brand-muted/70'
              }`}>
                {w.isWorking ? 'Duty' : 'Off'}
              </span>
            </button>
          ))}
        </div>

        {/* Working Day & Schedule Status Banner */}
        <div className="mt-4 p-3 rounded-xl bg-brand-ground/80 border border-brand-border/60 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-brand-text">Active Date:</span>
            <span className="font-semibold text-brand-deep">{formattedDisplayDate}</span>
            <Badge variant={isDoctorWorkingDay ? 'success' : 'neutral'} size="sm">
              {isDoctorWorkingDay ? 'Clinic Duty Day' : 'Doctor Off Duty'}
            </Badge>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium text-brand-muted">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span>Available</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-brand-primary" />
              <span>Booked ({dayAppointments.length})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-slate-400" />
              <span>Past Slot</span>
            </div>
          </div>
        </div>
      </div>

      {/* Slots Display Grid */}
      {isLoading ? (
        <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 shadow-clinical-xs space-y-4">
          <Skeleton className="h-6 w-48 rounded-lg" />
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-2xl" />
            ))}
          </div>
        </div>
      ) : error ? (
        <div className="bg-brand-surface rounded-3xl border border-brand-border p-6 shadow-clinical-xs text-center space-y-3">
          <ClinicalIcon name="alert" size={24} className="text-red-500 mx-auto" />
          <p className="text-sm font-semibold text-red-700">{error}</p>
          <Button size="sm" variant="outline" onClick={loadSchedule}>
            Retry Loading
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Morning Consultation Slots */}
          <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs space-y-4">
            <div className="flex items-center justify-between border-b border-brand-border/60 pb-3">
              <h3 className="text-sm font-bold text-brand-text uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Morning Consultation Session (09:00 AM &ndash; 12:30 PM)
              </h3>
              <span className="text-xs text-brand-muted font-medium">30-min intervals</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {morningSlots.map((slot) => {
                const appt = apptByTime[slot.time]
                const isBooked = slot.status === 'booked' || Boolean(appt)
                const isAvailable = slot.status === 'available' && !appt
                const isPast = slot.status === 'past' && !appt

                return (
                  <div
                    key={slot.time}
                    onClick={() => isBooked && appt && setSelectedApptModal(appt)}
                    className={`rounded-2xl p-3.5 border transition-all text-left relative overflow-hidden ${
                      isBooked
                        ? 'bg-teal-50/70 border-teal-200 text-teal-950 hover:border-teal-400 hover:shadow-xs cursor-pointer'
                        : isAvailable
                        ? 'bg-emerald-50/40 border-emerald-200/70 text-emerald-900'
                        : isPast
                        ? 'bg-brand-ground/70 border-brand-border text-brand-muted opacity-80'
                        : 'bg-brand-ground/50 border-brand-border/70 text-brand-muted'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-bold">
                        {formatSlotTime(slot.time)}
                      </span>
                      {isBooked ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-600 text-white">
                          Booked
                        </span>
                      ) : isAvailable ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                          Open
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                          {slot.status}
                        </span>
                      )}
                    </div>

                    {isBooked && appt ? (
                      <div className="space-y-0.5">
                        <p className="text-xs font-bold text-brand-text truncate">
                          {appt.patient?.full_name || 'Booked Patient'}
                        </p>
                        <p className="text-[10px] font-mono text-brand-muted truncate">
                          Ref: {appt.appointment_token || 'N/A'}
                        </p>
                      </div>
                    ) : (
                      <p className="text-[11px] text-brand-muted font-medium">
                        {isAvailable ? 'Available for patient booking' : 'Slot concluded or off-duty'}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Afternoon Consultation Slots */}
          <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs space-y-4">
            <div className="flex items-center justify-between border-b border-brand-border/60 pb-3">
              <h3 className="text-sm font-bold text-brand-text uppercase tracking-wider flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-teal-600" />
                Afternoon Consultation Session (02:00 PM &ndash; 05:00 PM)
              </h3>
              <span className="text-xs text-brand-muted font-medium">30-min intervals</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {afternoonSlots.map((slot) => {
                const appt = apptByTime[slot.time]
                const isBooked = slot.status === 'booked' || Boolean(appt)
                const isAvailable = slot.status === 'available' && !appt
                const isPast = slot.status === 'past' && !appt

                return (
                  <div
                    key={slot.time}
                    onClick={() => isBooked && appt && setSelectedApptModal(appt)}
                    className={`rounded-2xl p-3.5 border transition-all text-left relative overflow-hidden ${
                      isBooked
                        ? 'bg-teal-50/70 border-teal-200 text-teal-950 hover:border-teal-400 hover:shadow-xs cursor-pointer'
                        : isAvailable
                        ? 'bg-emerald-50/40 border-emerald-200/70 text-emerald-900'
                        : isPast
                        ? 'bg-brand-ground/70 border-brand-border text-brand-muted opacity-80'
                        : 'bg-brand-ground/50 border-brand-border/70 text-brand-muted'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-mono font-bold">
                        {formatSlotTime(slot.time)}
                      </span>
                      {isBooked ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-600 text-white">
                          Booked
                        </span>
                      ) : isAvailable ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                          Open
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                          {slot.status}
                        </span>
                      )}
                    </div>

                    {isBooked && appt ? (
                      <div className="space-y-0.5">
                        <p className="text-xs font-bold text-brand-text truncate">
                          {appt.patient?.full_name || 'Booked Patient'}
                        </p>
                        <p className="text-[10px] font-mono text-brand-muted truncate">
                          Ref: {appt.appointment_token || 'N/A'}
                        </p>
                      </div>
                    ) : (
                      <p className="text-[11px] text-brand-muted font-medium">
                        {isAvailable ? 'Available for patient booking' : 'Slot concluded or off-duty'}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Appointment Detail Modal */}
      {selectedApptModal && (
        <Modal
          isOpen={Boolean(selectedApptModal)}
          onClose={() => setSelectedApptModal(null)}
          size="md"
        >
          <ModalHeader
            title="Consultation Details"
            subtitle={`Reference Token: ${selectedApptModal.appointment_token}`}
            onClose={() => setSelectedApptModal(null)}
          />
          <ModalBody className="space-y-4">
            <div className="p-4 bg-brand-ground rounded-2xl border border-brand-border/70 space-y-2">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="text-sm font-bold text-brand-text">
                    {selectedApptModal.patient?.full_name || 'Patient'}
                  </h4>
                  <p className="text-xs text-brand-muted">
                    {selectedApptModal.patient?.email || 'No email registered'}
                  </p>
                  {selectedApptModal.patient?.phone && (
                    <p className="text-xs text-brand-muted">
                      Phone: {selectedApptModal.patient.phone}
                    </p>
                  )}
                </div>
                <Badge variant={selectedApptModal.status === 'completed' ? 'success' : 'teal'}>
                  {selectedApptModal.status?.toUpperCase()}
                </Badge>
              </div>

              <div className="pt-2 border-t border-brand-border/60 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-brand-muted block font-medium">Date</span>
                  <span className="font-bold text-brand-text">{selectedApptModal.appointment_date}</span>
                </div>
                <div>
                  <span className="text-brand-muted block font-medium">Scheduled Time</span>
                  <span className="font-bold text-brand-text">{formatSlotTime(selectedApptModal.appointment_time)}</span>
                </div>
              </div>
            </div>

            {selectedApptModal.problem_description && (
              <div className="space-y-1">
                <span className="text-xs font-bold text-brand-muted uppercase tracking-wider">
                  Patient Symptoms / Problem
                </span>
                <p className="text-xs p-3 rounded-xl bg-white border border-brand-border text-brand-text">
                  {selectedApptModal.problem_description}
                </p>
              </div>
            )}
          </ModalBody>
          <ModalFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedApptModal(null)}
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
