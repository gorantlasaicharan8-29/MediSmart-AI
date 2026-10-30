import React from 'react'
import { Button, ClinicalIcon } from '../ui'

const COMMON_SPECIALTIES = [
  'Cardiology',
  'Neurology',
  'Oncology',
  'Orthopedics',
  'Pediatrics',
  'Nephrology',
  'General Medicine',
  'Emergency Medicine',
]

export default function HospitalFilters({
  search = '',
  onSearchChange = () => {},
  selectedCity = '',
  onCityChange = () => {},
  selectedSpecialty = '',
  onSpecialtyChange = () => {},
  onlyMapped = false,
  onOnlyMappedChange = () => {},
  cities = [],
  onReset = () => {},
}) {
  const hasActiveFilters =
    Boolean(search) ||
    Boolean(selectedCity) ||
    Boolean(selectedSpecialty) ||
    onlyMapped

  return (
    <div className="bg-brand-surface rounded-2xl border border-brand-border p-4 sm:p-5 shadow-clinical-xs space-y-4">
      {/* Top Search & City Row */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
        {/* Search Input */}
        <div className="sm:col-span-7 relative">
          <div
            className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-brand-muted"
            aria-hidden="true"
          >
            <ClinicalIcon name="search" size={16} />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search hospitals by facility name, address, or city..."
            className="w-full pl-10 pr-9 py-2.5 rounded-xl border border-brand-border text-sm text-brand-text placeholder:text-brand-muted/70 focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-brand-accent bg-brand-ground transition-all"
          />
          {search && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-xs text-brand-muted hover:text-brand-text cursor-pointer"
              aria-label="Clear search query"
            >
              <ClinicalIcon name="x" size={14} ariaHidden="true" />
            </button>
          )}
        </div>

        {/* City Filter */}
        <div className="sm:col-span-5 relative">
          <label htmlFor="hospital-city-filter" className="sr-only">
            Filter by city
          </label>
          <select
            id="hospital-city-filter"
            value={selectedCity}
            onChange={(e) => onCityChange(e.target.value)}
            className="w-full h-11 px-3.5 pr-8 rounded-xl border border-brand-border text-xs font-semibold text-brand-text bg-brand-ground focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer"
          >
            <option value="">All Metropolitan Regions</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                {city}
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

      {/* Specialty Filter Chips */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-brand-text">
            Filter by Clinical Specialty
          </span>
          {hasActiveFilters && (
            <Button
              variant="link"
              size="sm"
              onClick={onReset}
              className="text-xs font-bold text-brand-accent hover:text-brand-deep"
            >
              Reset Filters
            </Button>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {COMMON_SPECIALTIES.map((spec) => {
            const isSelected = selectedSpecialty === spec
            return (
              <button
                key={spec}
                type="button"
                onClick={() => onSpecialtyChange(isSelected ? '' : spec)}
                className={`text-xs px-3 py-1.5 rounded-xl transition-all font-medium cursor-pointer ${
                  isSelected
                    ? 'bg-brand-primary text-white shadow-clinical-xs'
                    : 'bg-brand-ground text-brand-muted hover:text-brand-text hover:bg-brand-mint/60 border border-brand-border/70'
                }`}
              >
                {spec}
              </button>
            )
          })}
        </div>
      </div>

      {/* Mapped Only Toggle */}
      <div className="pt-2 border-t border-brand-border/70 flex items-center justify-between text-xs">
        <label className="flex items-center gap-2 cursor-pointer font-medium text-brand-text select-none">
          <input
            type="checkbox"
            checked={onlyMapped}
            onChange={(e) => onOnlyMappedChange(e.target.checked)}
            className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-accent cursor-pointer accent-brand-primary"
          />
          <span>Show facilities with interactive map coordinates only</span>
        </label>

        <span className="text-[11px] text-brand-muted hidden sm:inline">
          OpenStreetMap Geocoded
        </span>
      </div>
    </div>
  )
}
