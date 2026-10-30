import React, { useState, useEffect } from 'react'
import { getMyDoctorProfile, updateMyDoctorProfile } from '../../services/api'
import { Button, Badge, ClinicalIcon, Skeleton } from '../../components/ui'

const ALL_DAYS = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

export default function DoctorProfile() {
  const [profile, setProfile] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Editable fields form state
  const [bio, setBio] = useState('')
  const [consultationFee, setConsultationFee] = useState('')
  const [isAvailable, setIsAvailable] = useState(true)
  const [availableDays, setAvailableDays] = useState([])

  const loadProfile = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getMyDoctorProfile()
      setProfile(data)
      setBio(data.bio || '')
      setConsultationFee(data.consultation_fee !== undefined ? String(data.consultation_fee) : '1000')
      setIsAvailable(data.is_available ?? true)
      setAvailableDays(data.available_days || ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    } catch (err) {
      setError(err.message || 'Failed to load doctor profile')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadProfile()
  }, [])

  const toggleDay = (day) => {
    if (availableDays.includes(day)) {
      setAvailableDays(availableDays.filter((d) => d !== day))
    } else {
      setAvailableDays([...availableDays, day])
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setSaveError(null)
    setSaveSuccess(null)

    const feeNum = parseFloat(consultationFee)
    if (isNaN(feeNum) || feeNum < 0) {
      setSaveError('Consultation fee must be a valid positive amount.')
      setIsSubmitting(false)
      return
    }

    try {
      const updated = await updateMyDoctorProfile({
        bio: bio.trim(),
        consultation_fee: feeNum,
        is_available: isAvailable,
        available_days: availableDays,
      })
      setProfile(updated)
      setSaveSuccess('Doctor profile updated successfully!')
      setTimeout(() => setSaveSuccess(null), 4000)
    } catch (err) {
      setSaveError(err.message || 'Failed to save changes')
    } finally {
      setIsSubmitting(false)
    }
  }

  const initials = (profile?.user?.full_name || 'DR')
    .replace('Dr. ', '')
    .split(' ')
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-brand-primary" />
            <span className="text-xs font-bold text-brand-primary uppercase tracking-wider">
              Clinical Credentials &amp; Practice Settings
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            My Doctor Profile
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-0.5">
            Manage your practice bio, clinic fee, availability status, and weekly working days
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={loadProfile}
          className="text-xs self-start sm:self-auto"
        >
          <ClinicalIcon name="activity" size={14} className="mr-1.5" />
          Refresh
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-44 w-full rounded-3xl" />
          <Skeleton className="h-72 w-full rounded-3xl" />
        </div>
      ) : error ? (
        <div className="p-8 text-center bg-brand-surface rounded-3xl border border-brand-border space-y-3">
          <ClinicalIcon name="alert" size={24} className="text-red-500 mx-auto" />
          <p className="text-sm font-semibold text-red-700">{error}</p>
          <Button size="sm" variant="outline" onClick={loadProfile}>
            Retry
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* 1. Doctor Identity Card (Read-Only Verified Profile) */}
          <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-6 shadow-clinical-xs relative overflow-hidden">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-brand-mint text-brand-deep border border-teal-200 flex items-center justify-center text-xl sm:text-2xl font-extrabold shadow-clinical-xs shrink-0 select-none">
                {initials}
              </div>

              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-xl sm:text-2xl font-extrabold text-brand-text">
                    {profile.user?.full_name?.startsWith('Dr.')
                      ? profile.user.full_name
                      : `Dr. ${profile.user?.full_name}`}
                  </h2>
                  <Badge variant="teal" size="sm">
                    {profile.specialty}
                  </Badge>
                  <Badge variant="success" size="sm">
                    Verified Practitioner
                  </Badge>
                </div>

                <p className="text-xs sm:text-sm text-brand-muted font-medium">
                  {profile.hospital?.name || 'All India Institute of Medical Sciences (AIIMS)'} &bull; {profile.hospital?.city || 'New Delhi'}
                </p>

                <div className="flex flex-wrap items-center gap-4 text-xs text-brand-muted pt-1">
                  <span>
                    <strong>Experience:</strong> {profile.experience_years} years
                  </span>
                  <span>
                    <strong>Qualification:</strong> {profile.qualification}
                  </span>
                  <span>
                    <strong>Status:</strong> {profile.credential_status?.toUpperCase() || 'VERIFIED'}
                  </span>
                </div>
              </div>
            </div>

            {/* Read-Only Institutional Protection Notice */}
            <div className="mt-5 p-3 rounded-xl bg-brand-ground/70 border border-brand-border/60 flex items-center gap-2.5 text-xs text-brand-muted">
              <ClinicalIcon name="info" size={14} className="text-brand-primary shrink-0" />
              <span>
                Medical council registration number, institutional affiliation, and clinical qualifications are officially verified and locked against unauthorized modification.
              </span>
            </div>
          </div>

          {/* 2. Practice Settings Form (Editable by Doctor) */}
          <form
            onSubmit={handleSave}
            className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-6 shadow-clinical-xs space-y-6"
          >
            <div className="border-b border-brand-border/70 pb-4 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-brand-text">
                  Practice Settings &amp; Availability
                </h3>
                <p className="text-xs text-brand-muted mt-0.5">
                  Customize the information displayed on your public patient booking card
                </p>
              </div>

              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                  isAvailable
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-red-50 text-red-800 border border-red-200'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    isAvailable ? 'bg-emerald-500' : 'bg-red-500'
                  }`}
                />
                {isAvailable ? 'Accepting Patients' : 'Consultations Paused'}
              </span>
            </div>

            {/* Feedback Notifications */}
            {saveSuccess && (
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2">
                <ClinicalIcon name="check" size={16} className="text-emerald-600 shrink-0" />
                <span>{saveSuccess}</span>
              </div>
            )}
            {saveError && (
              <div className="p-3.5 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs flex items-center gap-2">
                <ClinicalIcon name="alert" size={16} className="text-red-600 shrink-0" />
                <span>{saveError}</span>
              </div>
            )}

            {/* Availability Toggle */}
            <div className="flex items-center justify-between p-4 rounded-2xl bg-brand-ground border border-brand-border/70">
              <div>
                <h4 className="text-xs font-bold text-brand-text">
                  Active Consultation Availability
                </h4>
                <p className="text-[11px] text-brand-muted mt-0.5">
                  When toggled off, patients will not be able to book new appointment slots.
                </p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isAvailable}
                  onChange={(e) => setIsAvailable(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-primary"></div>
              </label>
            </div>

            {/* Consultation Fee */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-brand-text uppercase tracking-wider">
                Consultation Fee (₹ INR)
              </label>
              <div className="relative max-w-xs">
                <span className="absolute left-3.5 top-2.5 text-brand-muted font-bold text-sm">
                  ₹
                </span>
                <input
                  type="number"
                  min="0"
                  step="50"
                  value={consultationFee}
                  onChange={(e) => setConsultationFee(e.target.value)}
                  className="w-full pl-8 pr-4 py-2 text-sm bg-white border border-brand-border rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text font-bold"
                  required
                />
              </div>
              <p className="text-[11px] text-brand-muted">
                Standard OPD consultation charge per 30-minute clinical session
              </p>
            </div>

            {/* Working Days Selector */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-brand-text uppercase tracking-wider">
                Weekly OPD Working Days
              </label>
              <p className="text-[11px] text-brand-muted">
                Select the days of the week when your OPD consultation slots are scheduled
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {ALL_DAYS.map((day) => {
                  const selected = availableDays.includes(day)
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => toggleDay(day)}
                      className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                        selected
                          ? 'bg-brand-primary text-white border border-brand-primary shadow-xs'
                          : 'bg-brand-ground text-brand-muted border border-brand-border hover:bg-white hover:text-brand-text'
                      }`}
                    >
                      {day}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Doctor Clinical Bio */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-brand-text uppercase tracking-wider">
                Clinical Biography &amp; Areas of Interest
              </label>
              <textarea
                rows={4}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Describe your medical expertise, specializations, surgical procedures, or patient care philosophy..."
                className="w-full p-3 text-xs bg-white border border-brand-border rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-accent/50 text-brand-text resize-none"
              />
            </div>

            {/* Save Button */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-brand-border/70">
              <Button
                type="submit"
                variant="primary"
                size="md"
                disabled={isSubmitting}
                className="text-xs font-bold px-6 py-2.5 bg-brand-primary hover:bg-brand-deep text-white cursor-pointer shadow-xs"
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Saving Changes...
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <ClinicalIcon name="check" size={14} />
                    Save Practice Settings
                  </span>
                )}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
