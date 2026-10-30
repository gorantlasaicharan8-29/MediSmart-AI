import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { bookAppointment, getDoctorSlots } from '../../services/api'
import {
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Badge,
  Input,
  ClinicalIcon,
  Skeleton,
} from '../ui'

const getTodayStr = () => new Date().toISOString().split('T')[0]

// Helper to get formatted date string for offset days
function getDateOffsetStr(daysAhead = 0) {
  const d = new Date()
  d.setDate(d.getDate() + daysAhead)
  return d.toISOString().split('T')[0]
}

// Format 24h "HH:MM" into "h:mm AM/PM"
function formatSlotTime(timeStr) {
  if (!timeStr) return ''
  const [hourStr, minStr] = timeStr.split(':')
  const hour = parseInt(hourStr, 10)
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${minStr} ${ampm}`
}

export default function BookingModal({ doctor, onClose, onSuccess }) {
  const { user } = useAuth()
  const todayStr = getTodayStr()

  const [selectedDate, setSelectedDate] = useState(todayStr)
  const [selectedTime, setSelectedTime] = useState('')
  const [notes, setNotes] = useState('')
  const [slotsData, setSlotsData] = useState(null)
  const [isLoadingSlots, setIsLoadingSlots] = useState(true)
  const [slotsError, setSlotsError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [conflictNotice, setConflictNotice] = useState(null)
  const [confirmedAppointment, setConfirmedAppointment] = useState(null)
  const [copiedToken, setCopiedToken] = useState(false)

  // Quick date options
  const dateOptions = [
    { label: 'Today', date: todayStr },
    { label: 'Tomorrow', date: getDateOffsetStr(1) },
    { label: 'In 2 Days', date: getDateOffsetStr(2) },
  ]

  // Fetch slots whenever selectedDate or doctor.id changes
  useEffect(() => {
    let ignore = false

    const fetchSlots = async () => {
      setIsLoadingSlots(true)
      try {
        const data = await getDoctorSlots(doctor.id, selectedDate)
        if (!ignore) {
          setSlotsData(data)
          setSlotsError(null)
          setError(null)
          setConflictNotice(null)
        }
      } catch (err) {
        if (!ignore) {
          const msg =
            err.status === 500
              ? 'Unable to load consultation availability due to a temporary server issue.'
              : err.message || 'Failed to load doctor slots'
          setSlotsError(msg)
          setError(msg)
        }
      } finally {
        if (!ignore) {
          setIsLoadingSlots(false)
        }
      }
    }

    fetchSlots()
    return () => {
      ignore = true
    }
  }, [doctor.id, selectedDate])

  const refreshSlots = useCallback(async () => {
    setIsLoadingSlots(true)
    try {
      const data = await getDoctorSlots(doctor.id, selectedDate)
      setSlotsData(data)
      setSlotsError(null)
      setError(null)
    } catch (err) {
      const msg =
        err.status === 500
          ? 'Unable to load consultation availability due to a temporary server issue.'
          : err.message || 'Failed to refresh doctor slots'
      setSlotsError(msg)
      setError(msg)
    } finally {
      setIsLoadingSlots(false)
    }
  }, [doctor.id, selectedDate])

  // Handle slot booking submit
  const handleBooking = async (e) => {
    e.preventDefault()
    if (!selectedTime) {
      setError('Please select an available appointment time slot.')
      return
    }

    setIsSubmitting(true)
    setError(null)
    setConflictNotice(null)

    try {
      const result = await bookAppointment({
        doctor_id: doctor.id,
        appointment_date: selectedDate,
        appointment_time: selectedTime,
        notes: notes.trim() || null,
      })

      setConfirmedAppointment(result)
      if (onSuccess) {
        onSuccess(result)
      }
    } catch (err) {
      if (err.status === 409) {
        // Step 3.D: Booking conflict handling
        setConflictNotice(
          `The slot at ${formatSlotTime(selectedTime)} was just booked by another patient. Please choose another available slot.`
        )
        // Invalidate conflicting selection
        setSelectedTime('')
        // Refresh available slots from backend
        refreshSlots()
      } else {
        const msg =
          err.status === 500
            ? 'Unable to complete consultation booking due to a temporary server issue. Please try again.'
            : err.message || 'Failed to book appointment. Please try again.'
        setError(msg)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Copy token to clipboard
  const handleCopyToken = () => {
    if (confirmedAppointment?.appointment_token) {
      navigator.clipboard.writeText(confirmedAppointment.appointment_token)
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    }
  }

  const doctorUser = doctor?.user || {}
  const hospital = doctor?.hospital || {}

  // Filter slots into morning and afternoon groups
  const allSlots = slotsData?.slots || []
  const morningSlots = allSlots.filter((s) => s.time < '13:00')
  const afternoonSlots = allSlots.filter((s) => s.time >= '13:00')

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      size="lg"
      showCloseButton={false}
      className="max-h-[92vh] overflow-hidden"
    >
      {/* Modal Header */}
      <ModalHeader onClose={onClose} showCloseButton={true}>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Badge variant={confirmedAppointment ? 'success' : 'teal'} size="sm">
              <ClinicalIcon
                name={confirmedAppointment ? 'check-circle' : 'calendar'}
                size={12}
                ariaHidden="true"
              />
              <span className="ml-1">
                {confirmedAppointment ? 'Booking Confirmed' : 'Consultation Scheduling'}
              </span>
            </Badge>
          </div>
          <h2 className="text-lg font-bold text-brand-text">
            {confirmedAppointment ? 'Your Consultation is Confirmed!' : 'Book Doctor Consultation'}
          </h2>
          <p className="text-xs text-brand-muted">
            {doctorUser.full_name || 'Medical Specialist'} • {doctor.specialty}
          </p>
        </div>
      </ModalHeader>

      {/* Modal Body */}
      <ModalBody className="space-y-5">
        {confirmedAppointment ? (
          /* ============================================================ */
          /* SUCCESS VIEW (Step 3.C)                                      */
          /* ============================================================ */
          <div className="space-y-6 py-2 text-center">
            {/* Success Icon */}
            <div className="w-16 h-16 rounded-2xl bg-clinical-success-bg text-clinical-success flex items-center justify-center mx-auto shadow-clinical-xs border border-emerald-200">
              <ClinicalIcon name="check-circle" size={36} ariaHidden="true" />
            </div>

            <div className="space-y-1">
              <h3 className="text-xl font-bold text-brand-text">
                Appointment Reserved Successfully
              </h3>
              <p className="text-xs text-brand-muted max-w-md mx-auto">
                Your consultation has been confirmed in the hospital system. Please save your unique appointment token for check-in and queue tracking.
              </p>
            </div>

            {/* Prominent Unique Token Box */}
            <div className="bg-brand-ground p-5 rounded-2xl border border-brand-border space-y-3">
              <span className="text-[11px] font-bold text-brand-muted uppercase tracking-widest block">
                Unique Appointment Token
              </span>
              <div className="flex items-center justify-center gap-3">
                <span className="font-mono text-2xl sm:text-3xl font-extrabold text-brand-deep tracking-wider select-all">
                  {confirmedAppointment.appointment_token}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyToken}
                  className="text-xs font-semibold gap-1.5"
                >
                  <ClinicalIcon
                    name={copiedToken ? 'check' : 'copy'}
                    size={14}
                    ariaHidden="true"
                  />
                  <span>{copiedToken ? 'Copied' : 'Copy'}</span>
                </Button>
              </div>
              <p className="text-[11px] text-brand-muted">
                Present this reference token upon arrival at the clinic counter or use it to self-check-in on your appointment day.
              </p>
            </div>

            {/* Appointment Summary Grid */}
            <div className="bg-brand-surface rounded-2xl p-4 text-xs text-brand-muted grid grid-cols-2 sm:grid-cols-4 gap-3 text-left border border-brand-border">
              <div>
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Specialist</span>
                <span className="font-semibold text-brand-text truncate block">
                  {doctorUser.full_name || 'Doctor'}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Hospital</span>
                <span className="font-semibold text-brand-text truncate block">
                  {hospital.name || 'Hospital Clinic'}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Date</span>
                <span className="font-semibold text-brand-text block">
                  {confirmedAppointment.appointment_date}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-brand-muted block">Time Slot</span>
                <span className="font-bold text-brand-primary block">
                  {formatSlotTime(confirmedAppointment.appointment_time)}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                variant="primary"
                size="md"
                as={Link}
                to="/appointments"
                onClick={onClose}
                className="font-bold text-xs"
              >
                View My Appointments
              </Button>
              {confirmedAppointment.appointment_date === todayStr && (
                <Button
                  variant="outline"
                  size="md"
                  as={Link}
                  to="/queue"
                  onClick={onClose}
                  className="font-semibold text-xs"
                >
                  Check In & Track Queue
                </Button>
              )}
              <Button
                variant="ghost"
                size="md"
                onClick={onClose}
                className="font-semibold text-xs"
              >
                Done
              </Button>
            </div>
          </div>
        ) : (
          /* ============================================================ */
          /* BOOKING FORM VIEW (Step 3.A, 3.B, 3.D)                      */
          /* ============================================================ */
          <form id="booking-form" onSubmit={handleBooking} className="space-y-5">
            {/* Authentication Alert */}
            {!user && (
              <div
                role="alert"
                className="p-3.5 rounded-xl bg-clinical-warning-bg border border-clinical-warning-border text-xs text-clinical-warning flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2">
                  <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
                  <span>You must be signed in to book a doctor consultation.</span>
                </div>
                <Link
                  to="/login"
                  className="font-bold underline text-brand-deep hover:text-brand-text shrink-0"
                >
                  Sign In
                </Link>
              </div>
            )}

            {/* Slot Conflict Alert (Step 3.D) */}
            {conflictNotice && (
              <div
                role="alert"
                className="p-3.5 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-start gap-2.5"
              >
                <ClinicalIcon
                  name="alert-triangle"
                  size={16}
                  className="shrink-0 text-clinical-danger mt-0.5"
                  ariaHidden="true"
                />
                <div className="space-y-1">
                  <p className="font-bold">Slot No Longer Available</p>
                  <p className="leading-relaxed">{conflictNotice}</p>
                </div>
              </div>
            )}

            {/* General Error Banner */}
            {error && !conflictNotice && (
              <div
                role="alert"
                className="p-3.5 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between gap-3"
              >
                <div className="flex items-center gap-2">
                  <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" className="shrink-0" />
                  <span className="font-medium">{error}</span>
                </div>
                {slotsError && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={refreshSlots}
                    disabled={isLoadingSlots}
                    className="shrink-0 text-xs py-1 px-3 border-clinical-danger/30 hover:bg-clinical-danger/10 text-clinical-danger"
                  >
                    Retry
                  </Button>
                )}
              </div>
            )}

            {/* Doctor Context Summary (Step 3.A) */}
            <div className="bg-brand-ground p-3.5 rounded-2xl border border-brand-border flex items-center justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-11 h-11 rounded-xl bg-brand-mint text-brand-deep font-bold flex items-center justify-center text-base border border-teal-200 shrink-0 select-none">
                  {doctorUser.full_name ? doctorUser.full_name.replace('Dr. ', '').charAt(0) : 'D'}
                </div>
                <div className="min-w-0">
                  <h4 className="text-sm font-bold text-brand-text truncate">
                    {doctorUser.full_name || 'Medical Specialist'}
                  </h4>
                  <p className="text-xs text-brand-muted truncate">
                    {hospital.name || 'Hospital Clinic'}
                    {hospital.city ? ` • ${hospital.city}` : ''}
                  </p>
                </div>
              </div>
              {typeof doctor.consultation_fee === 'number' && (
                <div className="text-right shrink-0">
                  <span className="text-[10px] uppercase font-bold text-brand-muted block">Fee</span>
                  <span className="text-sm font-extrabold text-brand-text">
                    ₹{doctor.consultation_fee.toFixed(0)}
                  </span>
                </div>
              )}
            </div>

            {/* Date Selection */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="appointment-date-input"
                  className="block text-xs font-bold text-brand-text uppercase tracking-wider"
                >
                  Select Consultation Date
                </label>
                <div className="flex items-center gap-1.5">
                  {dateOptions.map((opt) => (
                    <button
                      key={opt.date}
                      type="button"
                      onClick={() => {
                        setSelectedTime('')
                        setSelectedDate(opt.date)
                      }}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                        selectedDate === opt.date
                          ? 'bg-brand-primary text-white shadow-clinical-xs'
                          : 'bg-brand-ground hover:bg-stone-200 text-brand-muted border border-brand-border'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <Input
                id="appointment-date-input"
                type="date"
                min={todayStr}
                value={selectedDate}
                onChange={(e) => {
                  setSelectedTime('')
                  setSelectedDate(e.target.value)
                }}
                className="w-full font-medium"
              />
            </div>

            {/* Slot Selection Grid (Step 3.B) */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold text-brand-text uppercase tracking-wider">
                  Available Slots (30-min intervals)
                </label>
                {slotsData && (
                  <span className="text-xs text-brand-muted font-medium">
                    {slotsData.day_of_week}
                  </span>
                )}
              </div>

              {isLoadingSlots ? (
                <div className="py-8 space-y-3">
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                      <Skeleton key={i} className="h-12 rounded-xl" />
                    ))}
                  </div>
                  <p className="text-center text-xs text-brand-muted animate-pulse">
                    Retrieving clinic availability...
                  </p>
                </div>
              ) : slotsError ? (
                <div className="py-6 text-center text-xs text-brand-muted bg-brand-ground rounded-2xl border border-brand-border p-4 space-y-3">
                  <div className="w-8 h-8 rounded-full bg-red-100 text-clinical-danger flex items-center justify-center mx-auto">
                    <ClinicalIcon name="alert-triangle" size={16} ariaHidden="true" />
                  </div>
                  <div className="space-y-1">
                    <p className="font-bold text-brand-text">Unable to Load Slots</p>
                    <p className="max-w-sm mx-auto">{slotsError}</p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={refreshSlots}
                    disabled={isLoadingSlots}
                    className="text-xs py-1.5 px-4"
                  >
                    Retry Availability Check
                  </Button>
                </div>
              ) : slotsData && !slotsData.is_working_day ? (
                <div className="py-6 text-center text-xs text-brand-muted bg-brand-ground rounded-2xl border border-brand-border p-4 space-y-1">
                  <div className="w-8 h-8 rounded-full bg-stone-200 text-stone-600 flex items-center justify-center mx-auto mb-2">
                    <ClinicalIcon name="calendar" size={16} ariaHidden="true" />
                  </div>
                  <p className="font-bold text-brand-text">Doctor Not Available</p>
                  <p className="max-w-sm mx-auto">
                    {doctorUser.full_name || 'This doctor'} does not hold clinic hours on {slotsData.day_of_week}s. Please choose another date.
                  </p>
                </div>
              ) : allSlots.length === 0 ? (
                <div className="py-6 text-center text-xs text-brand-muted bg-brand-ground rounded-2xl border border-brand-border p-4">
                  <p className="font-semibold text-brand-text mb-1">No Consultation Slots</p>
                  <p>No slots are scheduled for this date. Please select a different date.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {allSlots.every((s) => !s.is_available) && (
                    <div className="p-3 rounded-xl bg-stone-100 border border-stone-200 text-xs text-stone-600 flex items-center gap-2">
                      <ClinicalIcon name="clock" size={16} className="text-stone-500 shrink-0" ariaHidden="true" />
                      <span>All consultation slots for this date are fully booked or have passed. Please select another date.</span>
                    </div>
                  )}

                  {/* Morning Slots */}
                  {morningSlots.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-bold text-brand-muted uppercase tracking-wider block">
                        Morning Slots
                      </span>
                      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                        {morningSlots.map((slot) => {
                          const isSelected = selectedTime === slot.time
                          return (
                            <button
                              key={slot.time}
                              type="button"
                              disabled={!slot.is_available}
                              onClick={() => {
                                setSelectedTime(slot.time)
                                setConflictNotice(null)
                              }}
                              aria-pressed={isSelected}
                              className={`py-2 px-1 text-center rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                                isSelected
                                  ? 'bg-brand-primary text-white shadow-clinical-sm ring-2 ring-brand-primary ring-offset-2'
                                  : slot.is_available
                                  ? 'bg-brand-mint/40 hover:bg-brand-mint text-brand-deep border border-teal-200/80 hover:border-brand-primary'
                                  : 'bg-stone-100 text-stone-400 border border-stone-200 cursor-not-allowed opacity-50'
                              }`}
                            >
                              <div className="font-bold">{formatSlotTime(slot.time)}</div>
                              <div className="text-[9px] font-normal tracking-tight">
                                {slot.is_available
                                  ? 'Available'
                                  : slot.status === 'past'
                                  ? 'Passed'
                                  : 'Booked'}
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Afternoon Slots */}
                  {afternoonSlots.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-bold text-brand-muted uppercase tracking-wider block">
                        Afternoon Slots
                      </span>
                      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                        {afternoonSlots.map((slot) => {
                          const isSelected = selectedTime === slot.time
                          return (
                            <button
                              key={slot.time}
                              type="button"
                              disabled={!slot.is_available}
                              onClick={() => {
                                setSelectedTime(slot.time)
                                setConflictNotice(null)
                              }}
                              aria-pressed={isSelected}
                              className={`py-2 px-1 text-center rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                                isSelected
                                  ? 'bg-brand-primary text-white shadow-clinical-sm ring-2 ring-brand-primary ring-offset-2'
                                  : slot.is_available
                                  ? 'bg-brand-mint/40 hover:bg-brand-mint text-brand-deep border border-teal-200/80 hover:border-brand-primary'
                                  : 'bg-stone-100 text-stone-400 border border-stone-200 cursor-not-allowed opacity-50'
                              }`}
                            >
                              <div className="font-bold">{formatSlotTime(slot.time)}</div>
                              <div className="text-[9px] font-normal tracking-tight">
                                {slot.is_available
                                  ? 'Available'
                                  : slot.status === 'past'
                                  ? 'Passed'
                                  : 'Booked'}
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Consultation Notes */}
            <div className="space-y-1.5">
              <label
                htmlFor="booking-notes"
                className="block text-xs font-bold text-brand-text uppercase tracking-wider"
              >
                Symptoms / Consultation Notes (Optional)
              </label>
              <textarea
                id="booking-notes"
                rows="2"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Briefly describe reasons for consultation, current symptoms, or relevant health history..."
                maxLength={1000}
                className="w-full px-3.5 py-2.5 rounded-xl border border-brand-border bg-brand-ground/50 text-xs text-brand-text placeholder-brand-muted focus:bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent/20 focus:border-brand-accent transition-all resize-none"
              />
            </div>
          </form>
        )}
      </ModalBody>

      {/* Modal Footer */}
      {!confirmedAppointment && (
        <ModalFooter>
          <Button
            variant="ghost"
            size="md"
            onClick={onClose}
            className="text-xs font-semibold"
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            size="md"
            type="submit"
            form="booking-form"
            disabled={
              !user ||
              !selectedTime ||
              isSubmitting ||
              (slotsData && !slotsData.is_working_day) ||
              Boolean(slotsError)
            }
            isLoading={isSubmitting}
            className="text-xs font-bold"
          >
            Confirm Booking
          </Button>
        </ModalFooter>
      )}
    </Modal>
  )
}
