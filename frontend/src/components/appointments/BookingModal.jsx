import React, { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { bookAppointment, getDoctorSlots } from '../../services/api'

const getTodayStr = () => new Date().toISOString().split('T')[0]

export default function BookingModal({ doctor, onClose, onSuccess }) {
  const { user } = useAuth()
  const todayStr = getTodayStr()

  const [selectedDate, setSelectedDate] = useState(todayStr)
  const [selectedTime, setSelectedTime] = useState('')
  const [notes, setNotes] = useState('')
  const [slotsData, setSlotsData] = useState(null)
  const [isLoadingSlots, setIsLoadingSlots] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [confirmedAppointment, setConfirmedAppointment] = useState(null)
  const [copiedToken, setCopiedToken] = useState(false)

  // Fetch slots whenever selectedDate or doctor.id changes
  useEffect(() => {
    let ignore = false

    const fetchSlots = async () => {
      try {
        const data = await getDoctorSlots(doctor.id, selectedDate)
        if (!ignore) {
          setSlotsData(data)
          setError(null)
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || 'Failed to load doctor slots')
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
    } catch (err) {
      setError(err.message || 'Failed to load doctor slots')
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
        setError('This appointment time slot is already booked. Please choose another slot.')
        // Reload slots to show updated occupancy
        refreshSlots()
      } else {
        setError(err.message || 'Failed to book appointment. Please try again.')
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

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative w-full max-w-xl bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="px-6 py-5 bg-gradient-to-r from-teal-700 via-teal-800 to-cyan-900 text-white flex items-center justify-between">
          <div className="space-y-0.5">
            <h2 className="text-lg font-bold">
              {confirmedAppointment ? 'Booking Confirmed!' : 'Book Doctor Consultation'}
            </h2>
            <p className="text-xs text-teal-200">
              {doctor.user?.full_name} • {doctor.specialty}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition-colors text-sm"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {confirmedAppointment ? (
            /* Success View */
            <div className="space-y-6 text-center py-4">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto text-3xl shadow-inner">
                ✓
              </div>

              <div className="space-y-1">
                <h3 className="text-xl font-bold text-slate-900">Your Appointment is Scheduled</h3>
                <p className="text-xs text-slate-500">
                  Please save your unique appointment token for check-in and queue tracking.
                </p>
              </div>

              {/* Unique Reference Card */}
              <div className="bg-slate-50 border border-slate-200 p-5 rounded-2xl space-y-3">
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
                  Unique Appointment Token
                </span>
                <div className="flex items-center justify-center gap-3">
                  <span className="font-mono text-xl sm:text-2xl font-black text-teal-700 tracking-wider">
                    {confirmedAppointment.appointment_token}
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyToken}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-300 hover:border-teal-500 text-slate-700 hover:text-teal-700 shadow-sm transition-all"
                  >
                    {copiedToken ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </div>

              {/* Details Summary */}
              <div className="bg-slate-50/50 rounded-xl p-4 text-xs text-slate-600 grid grid-cols-2 gap-3 text-left border border-slate-100">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Doctor</span>
                  <span className="font-semibold text-slate-900">{doctor.user?.full_name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Hospital</span>
                  <span className="font-semibold text-slate-900 truncate block">{doctor.hospital?.name}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Date</span>
                  <span className="font-semibold text-slate-900">{confirmedAppointment.appointment_date}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Time</span>
                  <span className="font-semibold text-teal-700">{confirmedAppointment.appointment_time}</span>
                </div>
              </div>

              {/* Navigation Actions */}
              <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
                <Link
                  to="/appointments"
                  onClick={onClose}
                  className="px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-sm transition-all text-center"
                >
                  View My Appointments
                </Link>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition-all"
                >
                  Close
                </button>
              </div>
            </div>
          ) : (
            /* Booking Form View */
            <form onSubmit={handleBooking} className="space-y-5">
              {/* Not Logged In Notice */}
              {!user && (
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center justify-between gap-3">
                  <span>Please sign in to book your consultation.</span>
                  <Link
                    to="/login"
                    className="font-bold underline text-amber-900 hover:text-amber-950 shrink-0"
                  >
                    Log In
                  </Link>
                </div>
              )}

              {/* Error / Conflict Alert */}
              {error && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2">
                  <span className="text-base shrink-0">⚠️</span>
                  <span className="leading-relaxed font-medium">{error}</span>
                </div>
              )}

              {/* Date Selection */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                  Select Consultation Date
                </label>
                <input
                  type="date"
                  min={todayStr}
                  value={selectedDate}
                  onChange={(e) => {
                    setIsLoadingSlots(true)
                    setSelectedTime('')
                    setSelectedDate(e.target.value)
                  }}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
                />
              </div>

              {/* Slot Grid */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                    Available Consultation Slots (30 min)
                  </label>
                  {slotsData && (
                    <span className="text-[11px] text-slate-500">
                      {slotsData.day_of_week}
                    </span>
                  )}
                </div>

                {isLoadingSlots ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    <div className="inline-block w-5 h-5 border-2 border-teal-600 border-t-transparent rounded-full animate-spin mb-2"></div>
                    <p>Loading available slots...</p>
                  </div>
                ) : slotsData && !slotsData.is_working_day ? (
                  <div className="py-6 text-center text-xs text-slate-500 bg-slate-50 rounded-2xl border border-slate-200 p-4">
                    <p className="font-semibold text-slate-800 mb-1">Doctor Not Available</p>
                    <p>
                      {doctor.user?.full_name} does not have clinic hours on {slotsData.day_of_week}s. Please pick another date.
                    </p>
                  </div>
                ) : slotsData?.slots ? (
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-48 overflow-y-auto p-1">
                    {slotsData.slots.map((slot) => {
                      const isSelected = selectedTime === slot.time
                      return (
                        <button
                          key={slot.time}
                          type="button"
                          disabled={!slot.is_available}
                          onClick={() => setSelectedTime(slot.time)}
                          className={`py-2 px-1 text-center rounded-xl text-xs font-semibold transition-all ${
                            isSelected
                              ? 'bg-teal-600 text-white shadow-sm ring-2 ring-teal-600 ring-offset-1'
                              : slot.is_available
                              ? 'bg-teal-50/60 hover:bg-teal-100 text-teal-800 border border-teal-200/80 cursor-pointer'
                              : 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed opacity-60'
                          }`}
                        >
                          <div>{slot.time}</div>
                          <div className="text-[9px] font-normal tracking-tight">
                            {slot.is_available ? 'Available' : 'Occupied'}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                ) : null}
              </div>

              {/* Consultation Notes */}
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5 uppercase tracking-wider">
                  Symptoms / Medical Notes (Optional)
                </label>
                <textarea
                  rows="2"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Briefly describe reasons for consultation, current symptoms, or relevant health history..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-slate-50/50 text-xs text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
                  maxLength={1000}
                ></textarea>
              </div>

              {/* Form Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!user || !selectedTime || isSubmitting || (slotsData && !slotsData.is_working_day)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Confirming...</span>
                    </>
                  ) : (
                    <span>Confirm Booking</span>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
