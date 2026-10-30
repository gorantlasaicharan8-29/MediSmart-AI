import React from 'react'
import { Button, ClinicalIcon } from '../ui'

const SPECIALTIES = [
  'Cardiology',
  'Neurology',
  'Oncology',
  'Orthopedics',
  'Pediatrics',
  'Gastroenterology',
  'Nephrology',
  'Pulmonology',
  'Dermatology',
]

export default function DoctorFilters({
  filters,
  onChange,
  onReset,
  hospitals = [],
}) {
  const hasActiveFilters =
    Boolean(filters.search) ||
    Boolean(filters.specialty) ||
    Boolean(filters.hospital_id) ||
    Boolean(filters.credential_status) ||
    filters.available_only

  return (
    <div className="bg-brand-surface rounded-2xl border border-brand-border p-5 shadow-clinical-xs space-y-4">
      {/* Top Search Bar */}
      <div className="relative">
        <div
          className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-brand-muted"
          aria-hidden="true"
        >
          <ClinicalIcon name="search" size={16} />
        </div>
        <input
          type="search"
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          placeholder="Search by doctor name, specialty, qualification, or hospital..."
          className="w-full pl-10 pr-9 py-2.5 rounded-xl border border-brand-border bg-brand-ground text-sm text-brand-text placeholder:text-brand-muted/70 focus:bg-brand-surface focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-brand-accent transition-all"
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onChange({ search: '' })}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-brand-muted hover:text-brand-text cursor-pointer"
            aria-label="Clear doctor search"
          >
            <ClinicalIcon name="x" size={14} ariaHidden="true" />
          </button>
        )}
      </div>

      {/* Filter Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Specialty Select */}
        <div className="relative">
          <label
            htmlFor="doctor-specialty-filter"
            className="block text-xs font-bold text-brand-text mb-1"
          >
            Medical Specialty
          </label>
          <div className="relative">
            <select
              id="doctor-specialty-filter"
              value={filters.specialty}
              onChange={(e) => onChange({ specialty: e.target.value })}
              className="w-full h-10 px-3 pr-8 rounded-xl border border-brand-border bg-brand-ground text-xs font-medium text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer appearance-none"
            >
              <option value="">All Clinical Specialties</option>
              {SPECIALTIES.map((spec) => (
                <option key={spec} value={spec}>
                  {spec}
                </option>
              ))}
            </select>
            <div
              className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-brand-muted"
              aria-hidden="true"
            >
              <ClinicalIcon name="chevron-down" size={14} />
            </div>
          </div>
        </div>

        {/* Hospital Affiliation Select */}
        <div className="relative">
          <label
            htmlFor="doctor-hospital-filter"
            className="block text-xs font-bold text-brand-text mb-1"
          >
            Hospital Affiliation
          </label>
          <div className="relative">
            <select
              id="doctor-hospital-filter"
              value={filters.hospital_id}
              onChange={(e) => onChange({ hospital_id: e.target.value })}
              className="w-full h-10 px-3 pr-8 rounded-xl border border-brand-border bg-brand-ground text-xs font-medium text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer appearance-none truncate"
            >
              <option value="">All Affiliated Hospitals</option>
              {hospitals.map((hosp) => (
                <option key={hosp.id} value={hosp.id}>
                  {hosp.name} ({hosp.city})
                </option>
              ))}
            </select>
            <div
              className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-brand-muted"
              aria-hidden="true"
            >
              <ClinicalIcon name="chevron-down" size={14} />
            </div>
          </div>
        </div>

        {/* Credential Status Select */}
        <div className="relative">
          <label
            htmlFor="doctor-status-filter"
            className="block text-xs font-bold text-brand-text mb-1"
          >
            Verification Status
          </label>
          <div className="relative">
            <select
              id="doctor-status-filter"
              value={filters.credential_status}
              onChange={(e) => onChange({ credential_status: e.target.value })}
              className="w-full h-10 px-3 pr-8 rounded-xl border border-brand-border bg-brand-ground text-xs font-medium text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer appearance-none"
            >
              <option value="">All Specialist Profiles</option>
              <option value="verified">Verified Specialists Only</option>
              <option value="sample">Demonstration Records</option>
              <option value="pending_verification">Verification In Progress</option>
            </select>
            <div
              className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-brand-muted"
              aria-hidden="true"
            >
              <ClinicalIcon name="chevron-down" size={14} />
            </div>
          </div>
        </div>

        {/* Available Only & Reset Actions */}
        <div className="flex items-end justify-between gap-2 pt-1">
          <label className="flex items-center gap-2 cursor-pointer select-none py-2 font-medium text-brand-text text-xs">
            <input
              type="checkbox"
              checked={filters.available_only}
              onChange={(e) => onChange({ available_only: e.target.checked })}
              className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-accent cursor-pointer accent-brand-primary"
            />
            <span>Available Today</span>
          </label>

          {hasActiveFilters && (
            <Button
              variant="link"
              size="sm"
              onClick={onReset}
              className="text-xs font-bold text-brand-accent hover:text-brand-deep py-2"
            >
              Reset Filters
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
