import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getDoctorRecommendations, getHospitals } from '../../services/api'
import {
  Button,
  Input,
  Skeleton,
  EmptyState,
  ClinicalIcon,
} from '../ui'

const getTodayStr = () => new Date().toISOString().split('T')[0]

const COMMON_SPECIALTIES = [
  'Cardiology',
  'Neurology',
  'Oncology',
  'Orthopedics',
  'Pediatrics',
  'Gastroenterology',
  'Nephrology',
  'Pulmonology',
  'Dermatology',
  'General Medicine',
]

const BUDGET_PRESETS = [
  { label: 'Any Budget', value: '' },
  { label: 'Under ₹500', value: '500' },
  { label: 'Under ₹1000', value: '1000' },
  { label: 'Under ₹1500', value: '1500' },
  { label: 'Under ₹2500', value: '2500' },
]

function formatSlotTime(timeStr) {
  if (!timeStr) return ''
  const [hourStr, minStr] = timeStr.split(':')
  const hour = parseInt(hourStr, 10)
  const ampm = hour >= 12 ? 'PM' : 'AM'
  const hour12 = hour % 12 || 12
  return `${hour12}:${minStr} ${ampm}`
}

export default function DoctorRecommendationSection({ onSelectDoctorForBooking }) {
  const [todayStr] = useState(getTodayStr)

  // Form Preferences State
  const [specialty, setSpecialty] = useState('')
  const [city, setCity] = useState('')
  const [hospitalId, setHospitalId] = useState('')
  const [maxFee, setMaxFee] = useState('')
  const [preferredDate, setPreferredDate] = useState(todayStr)
  const [consultationType, setConsultationType] = useState('OPD / In-Person')

  // Data & Execution State
  const [hospitals, setHospitals] = useState([])
  const [recommendations, setRecommendations] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [hasSearched, setHasSearched] = useState(false)

  // Load hospitals for dropdown
  useEffect(() => {
    let ignore = false
    async function loadHospitals() {
      try {
        const data = await getHospitals({ limit: 100 })
        if (!ignore && data?.items) {
          setHospitals(data.items)
        }
      } catch {
        // Fallback silently if hospital list fails to load
      }
    }
    loadHospitals()
    return () => {
      ignore = true
    }
  }, [])

  const handleGetRecommendations = async (e) => {
    if (e) e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const payload = {
        specialty: specialty.trim() || undefined,
        city: city.trim() || undefined,
        hospital_id: hospitalId || undefined,
        max_fee: maxFee ? parseFloat(maxFee) : undefined,
        preferred_date: preferredDate || todayStr,
        consultation_type: consultationType,
        limit: 6,
      }

      const res = await getDoctorRecommendations(payload)
      setRecommendations(res)
      setHasSearched(true)
    } catch (err) {
      setError(err.message || 'Failed to generate recommendations. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setSpecialty('')
    setCity('')
    setHospitalId('')
    setMaxFee('')
    setPreferredDate(todayStr)
    setConsultationType('OPD / In-Person')
    setRecommendations(null)
    setHasSearched(false)
    setError(null)
  }

  return (
    <section
      aria-labelledby="recommendation-heading"
      className="rounded-3xl border border-stone-200 bg-gradient-to-b from-[#F8F9F7] to-white p-5 sm:p-7 shadow-sm transition-all"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-stone-200/80">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#CCFBF1] text-[#0D9488] border border-[#0D9488]/20">
              <ClinicalIcon name="sparkles" size={12} ariaHidden="true" />
              <span>AI Recommendation Engine</span>
            </span>
          </div>
          <h2
            id="recommendation-heading"
            className="text-xl sm:text-2xl font-extrabold text-brand-text tracking-tight"
          >
            Find Your Best-Matched Doctor
          </h2>
          <p className="text-xs sm:text-sm text-brand-muted mt-0.5">
            Discover specialists based on your healthcare preferences.
          </p>
        </div>

        {hasSearched && (
          <button
            type="button"
            onClick={handleReset}
            className="self-start sm:self-auto text-xs font-semibold text-brand-muted hover:text-[#0D9488] transition-colors flex items-center gap-1 cursor-pointer"
          >
            <ClinicalIcon name="refresh" size={13} ariaHidden="true" />
            <span>Reset Preferences</span>
          </button>
        )}
      </div>

      {/* Preferences Form */}
      <form onSubmit={handleGetRecommendations} className="mt-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* 1. Specialization */}
          <div>
            <label
              htmlFor="rec-specialty"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Medical Specialization
            </label>
            <select
              id="rec-specialty"
              value={specialty}
              onChange={(e) => setSpecialty(e.target.value)}
              className="w-full h-10 px-3 rounded-xl border border-stone-200 bg-white text-xs font-medium text-stone-800 focus:outline-none focus:ring-2 focus:ring-[#0D9488]/30 focus:border-[#0D9488]"
            >
              <option value="">All Specializations</option>
              {COMMON_SPECIALTIES.map((spec) => (
                <option key={spec} value={spec}>
                  {spec}
                </option>
              ))}
            </select>
          </div>

          {/* 2. Location / City */}
          <div>
            <label
              htmlFor="rec-city"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Preferred Location / City
            </label>
            <Input
              id="rec-city"
              type="text"
              placeholder="e.g. Hyderabad, Bengaluru, Mumbai"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="text-xs h-10 rounded-xl"
            />
          </div>

          {/* 3. Preferred Hospital */}
          <div>
            <label
              htmlFor="rec-hospital"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Preferred Hospital (Optional)
            </label>
            <select
              id="rec-hospital"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              className="w-full h-10 px-3 rounded-xl border border-stone-200 bg-white text-xs font-medium text-stone-800 focus:outline-none focus:ring-2 focus:ring-[#0D9488]/30 focus:border-[#0D9488]"
            >
              <option value="">Any Affiliated Hospital</option>
              {hospitals.map((hosp) => (
                <option key={hosp.id} value={hosp.id}>
                  {hosp.name} ({hosp.city})
                </option>
              ))}
            </select>
          </div>

          {/* 4. Consultation Budget */}
          <div>
            <label
              htmlFor="rec-fee"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Max Consultation Fee (₹)
            </label>
            <Input
              id="rec-fee"
              type="number"
              min="0"
              step="50"
              placeholder="e.g. 1500"
              value={maxFee}
              onChange={(e) => setMaxFee(e.target.value)}
              className="text-xs h-10 rounded-xl"
            />
          </div>

          {/* 5. Preferred Date */}
          <div>
            <label
              htmlFor="rec-date"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Preferred Consultation Date
            </label>
            <Input
              id="rec-date"
              type="date"
              min={todayStr}
              value={preferredDate}
              onChange={(e) => setPreferredDate(e.target.value)}
              className="text-xs h-10 rounded-xl"
            />
          </div>

          {/* 6. Consultation Type */}
          <div>
            <label
              htmlFor="rec-type"
              className="block text-xs font-bold text-stone-700 mb-1"
            >
              Consultation Type
            </label>
            <select
              id="rec-type"
              value={consultationType}
              onChange={(e) => setConsultationType(e.target.value)}
              className="w-full h-10 px-3 rounded-xl border border-stone-200 bg-white text-xs font-medium text-stone-800 focus:outline-none focus:ring-2 focus:ring-[#0D9488]/30 focus:border-[#0D9488]"
            >
              <option value="OPD / In-Person">OPD / In-Person Clinic</option>
              <option value="Teleconsultation / Video">Teleconsultation / Video</option>
            </select>
          </div>
        </div>

        {/* Budget Quick-Select Pills */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span className="text-[11px] font-semibold text-stone-500 mr-1">Quick Budget:</span>
          {BUDGET_PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => setMaxFee(p.value)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors cursor-pointer ${
                maxFee === p.value
                  ? 'bg-[#0D9488] text-white border-[#0D9488]'
                  : 'bg-white text-stone-600 border-stone-200 hover:border-stone-300 hover:bg-stone-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Submit Action */}
        <div className="pt-2 flex items-center justify-start">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={isLoading}
            className="w-full sm:w-auto font-bold text-xs gap-2 shadow-clinical-xs bg-[#0D9488] hover:bg-[#0F766E]"
          >
            {isLoading ? (
              <>
                <ClinicalIcon name="spinner" size={14} className="animate-spin" ariaHidden="true" />
                <span>Analyzing Doctors...</span>
              </>
            ) : (
              <>
                <ClinicalIcon name="sparkles" size={14} ariaHidden="true" />
                <span>Get AI Recommendations</span>
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="mt-5 p-4 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
            <span>{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleGetRecommendations}
            className="text-xs font-bold"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="mt-6 space-y-4">
          <p className="text-xs text-brand-muted animate-pulse font-semibold">
            Evaluating doctor availability, schedules, and clinical preferences...
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Skeleton.Card lines={4} />
            <Skeleton.Card lines={4} />
          </div>
        </div>
      )}

      {/* Recommendations Display */}
      {!isLoading && recommendations && (
        <div className="mt-7 pt-5 border-t border-stone-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-stone-800">
              Recommended Specialists ({recommendations.items?.length || 0} Matched)
            </h3>
            <span className="text-[11px] text-stone-500 font-medium">
              Evaluated on {recommendations.preferred_date}
            </span>
          </div>

          {recommendations.items?.length === 0 ? (
            <EmptyState
              icon="stethoscope"
              title="No Matching Doctors Found"
              description="No specialists met all of your selected criteria. Try selecting 'All Specializations', broadening your location, or adjusting your consultation fee budget."
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleReset}
                  className="text-xs font-bold gap-1"
                >
                  <ClinicalIcon name="refresh" size={12} ariaHidden="true" />
                  <span>Reset Filters</span>
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recommendations.items.map((item) => {
                const doc = item.doctor
                const docName = doc.user?.full_name || 'Medical Specialist'
                const hospName = doc.hospital?.name || 'Affiliated Hospital'
                const hospCity = doc.hospital?.city || 'Location'

                return (
                  <div
                    key={doc.id}
                    className="flex flex-col justify-between rounded-2xl border border-stone-200 bg-white p-5 hover:border-[#0D9488]/50 hover:shadow-clinical-sm transition-all relative overflow-hidden"
                  >
                    {/* Top Row: Doctor Info + Match Score Pill */}
                    <div>
                      <div className="flex items-start justify-between gap-3 mb-2.5">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-xl bg-[#CCFBF1] text-[#0D9488] flex items-center justify-center font-extrabold text-sm shrink-0 border border-[#0D9488]/20">
                            <ClinicalIcon name="stethoscope" size={18} ariaHidden="true" />
                          </div>
                          <div>
                            <h4 className="text-sm font-extrabold text-stone-900 leading-snug">
                              {docName}
                            </h4>
                            <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                              <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-teal-50 text-teal-800 border border-teal-200">
                                {doc.specialty}
                              </span>
                              {doc.experience_years > 0 && (
                                <span className="text-[11px] text-stone-500 font-semibold">
                                  {doc.experience_years} yrs exp
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Recommendation Match Score Badge */}
                        <div className="shrink-0 text-right">
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-extrabold bg-[#CCFBF1] text-[#0D9488] border border-[#0D9488]/30 shadow-xs">
                            <ClinicalIcon name="sparkles" size={12} ariaHidden="true" />
                            <span>{item.match_score}% Match</span>
                          </span>
                        </div>
                      </div>

                      {/* Hospital & Fee Metadata */}
                      <div className="space-y-1.5 text-xs text-stone-600 mt-2">
                        <div className="flex items-center gap-1.5">
                          <ClinicalIcon name="hospital" size={13} className="text-stone-400 shrink-0" ariaHidden="true" />
                          <span className="font-semibold text-stone-800">{hospName}</span>
                          <span className="text-stone-400">•</span>
                          <span>{hospCity}</span>
                        </div>

                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-1 font-semibold text-stone-700">
                            <span>Fee:</span>
                            <span className="text-stone-900 font-bold">
                              ₹{doc.consultation_fee != null ? Number(doc.consultation_fee).toFixed(0) : 'Standard'}
                            </span>
                          </div>
                          {doc.qualification && (
                            <span className="text-stone-500 truncate max-w-[180px]" title={doc.qualification}>
                              {doc.qualification}
                            </span>
                          )}
                        </div>

                        {/* Next Confirmed Slot Badge */}
                        <div className="pt-1">
                          {item.is_slot_available && item.next_available_slot ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                              <ClinicalIcon name="clock" size={12} ariaHidden="true" />
                              <span>
                                Next Slot: {formatSlotTime(item.next_available_slot)} ({recommendations.preferred_date})
                              </span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                              <ClinicalIcon name="alert-circle" size={12} ariaHidden="true" />
                              <span>No open slots on {recommendations.preferred_date}</span>
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Explainability Section */}
                      {item.explanations && item.explanations.length > 0 && (
                        <div className="mt-3.5 pt-3 border-t border-stone-100 bg-stone-50/60 rounded-xl p-2.5">
                          <p className="text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1.5">
                            Why this doctor matches:
                          </p>
                          <ul className="space-y-1">
                            {item.explanations.map((exp, i) => (
                              <li key={i} className="flex items-start gap-1.5 text-xs text-stone-700">
                                <ClinicalIcon
                                  name="check-circle"
                                  size={12}
                                  className="text-[#0D9488] shrink-0 mt-0.5"
                                  ariaHidden="true"
                                />
                                <span className="leading-tight">{exp}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Bottom Actions */}
                    <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        as={Link}
                        to={`/doctors?search=${encodeURIComponent(docName)}`}
                        className="text-xs font-bold text-stone-600 hover:text-stone-900 gap-1 px-2"
                      >
                        <ClinicalIcon name="eye" size={13} ariaHidden="true" />
                        <span>View Profile</span>
                      </Button>

                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => onSelectDoctorForBooking && onSelectDoctorForBooking(doc)}
                        className="text-xs font-bold gap-1.5 bg-[#0D9488] hover:bg-[#0F766E] shadow-clinical-xs"
                      >
                        <ClinicalIcon name="calendar" size={13} ariaHidden="true" />
                        <span>Book Consultation</span>
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
