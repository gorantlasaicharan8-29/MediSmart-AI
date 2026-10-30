import React from 'react'
import { Badge, Button, ClinicalIcon } from '../ui'

export default function DoctorCard({ doctor, onBook }) {
  const user = doctor.user || {}
  const hospital = doctor.hospital || {}

  // Determine credential provenance badge based strictly on backend field
  const renderCredentialBadge = () => {
    switch (doctor.credential_status) {
      case 'verified':
        return (
          <Badge
            variant="success"
            size="sm"
            icon={<ClinicalIcon name="check-circle" size={12} ariaHidden="true" />}
          >
            Verified Specialist
          </Badge>
        )
      case 'sample':
        return (
          <Badge
            variant="neutral"
            size="sm"
            icon={<ClinicalIcon name="info" size={12} ariaHidden="true" />}
          >
            Demonstration Profile
          </Badge>
        )
      case 'pending_verification':
      default:
        return (
          <Badge
            variant="warning"
            size="sm"
            icon={<ClinicalIcon name="clock" size={12} ariaHidden="true" />}
          >
            Verification In Progress
          </Badge>
        )
    }
  }

  return (
    <div className="group relative flex flex-col justify-between bg-brand-surface rounded-2xl border border-brand-border p-6 shadow-clinical-xs hover:shadow-clinical-sm transition-all duration-200">
      <div className="space-y-4">
        {/* Top Header: Specialty & Credential Badge */}
        <div className="flex items-start justify-between gap-2">
          <Badge variant="teal" size="md">
            {doctor.specialty}
          </Badge>
          {renderCredentialBadge()}
        </div>

        {/* Doctor Identity */}
        <div>
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-brand-mint text-brand-deep font-bold flex items-center justify-center text-lg border border-teal-200 shadow-clinical-xs select-none shrink-0">
              {user.full_name ? user.full_name.replace('Dr. ', '').charAt(0) : 'D'}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-base sm:text-lg font-bold text-brand-text group-hover:text-brand-deep transition-colors truncate">
                {user.full_name || 'Medical Specialist'}
              </h3>
              <p className="text-xs text-brand-muted line-clamp-1">
                {doctor.qualification || 'Certified Healthcare Professional'}
              </p>
            </div>
          </div>
        </div>

        {/* Hospital Affiliation */}
        <div className="pt-2 border-t border-brand-border/70 space-y-1 text-xs text-brand-muted">
          <div className="flex items-center gap-2">
            <ClinicalIcon
              name="hospital"
              size={14}
              className="text-brand-accent shrink-0"
              ariaHidden="true"
            />
            <span className="font-semibold text-brand-text truncate">
              {hospital.name || 'Hospital Affiliation Pending'}
            </span>
          </div>
          {hospital.city && (
            <div className="flex items-center gap-2 text-[11px] text-brand-muted pl-5">
              <span>
                {hospital.city}, {hospital.state}
              </span>
            </div>
          )}
        </div>

        {/* Bio */}
        {doctor.bio && (
          <p className="text-xs text-brand-muted line-clamp-2 leading-relaxed bg-brand-ground p-3 rounded-xl border border-brand-border/70">
            {doctor.bio}
          </p>
        )}

        {/* Clinical Stats */}
        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
          <div className="bg-brand-ground p-2.5 rounded-xl border border-brand-border/70">
            <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider">
              Experience
            </span>
            <span className="font-bold text-brand-text text-sm">
              {doctor.experience_years} Years
            </span>
          </div>
          <div className="bg-brand-ground p-2.5 rounded-xl border border-brand-border/70">
            <span className="text-brand-muted block text-[10px] uppercase font-bold tracking-wider">
              Consultation Fee
            </span>
            <span className="font-bold text-brand-primary text-sm">
              ₹{doctor.consultation_fee ? doctor.consultation_fee.toFixed(0) : 'Free'}
            </span>
          </div>
        </div>

        {/* Working Days */}
        {doctor.available_days && doctor.available_days.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-brand-muted font-bold uppercase tracking-wider block">
              Consultation Days
            </span>
            <div className="flex flex-wrap gap-1">
              {doctor.available_days.map((day) => (
                <span
                  key={day}
                  className="text-[10px] px-2 py-0.5 rounded-md bg-brand-ground text-brand-text border border-brand-border/70 font-semibold"
                >
                  {day.slice(0, 3)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="pt-5 mt-4 border-t border-brand-border/70 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              doctor.is_available ? 'bg-clinical-success animate-pulse' : 'bg-stone-300'
            }`}
            aria-hidden="true"
          />
          <span
            className={`font-semibold ${
              doctor.is_available ? 'text-clinical-success' : 'text-brand-muted'
            }`}
          >
            {doctor.is_available ? 'Accepting Patients' : 'Unavailable'}
          </span>
        </div>

        <Button
          variant="primary"
          size="sm"
          disabled={!doctor.is_available}
          onClick={() => onBook(doctor)}
          className="text-xs font-semibold"
        >
          Book Consultation
        </Button>
      </div>
    </div>
  )
}
