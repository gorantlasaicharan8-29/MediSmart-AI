import React from 'react'

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
    Boolean(search) || Boolean(selectedCity) || Boolean(selectedSpecialty) || onlyMapped

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-xs space-y-4">
      {/* Top Search & City Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
        {/* Search Input */}
        <div className="sm:col-span-7 relative">
          <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            🔍
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search hospitals by name, city, address..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white placeholder:text-slate-400"
          />
        </div>

        {/* City Filter */}
        <div className="sm:col-span-5">
          <select
            value={selectedCity}
            onChange={(e) => onCityChange(e.target.value)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white text-slate-700"
          >
            <option value="">All Metropolitan Regions</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                {city}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Specialty Filter Chips */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-700">Filter by Specialty</span>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onReset}
              className="text-xs text-teal-600 hover:text-teal-700 font-semibold"
            >
              Reset Filters
            </button>
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
                className={`text-xs px-3 py-1.5 rounded-xl transition-all font-medium ${
                  isSelected
                    ? 'bg-teal-600 text-white shadow-xs'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200/60'
                }`}
              >
                {spec}
              </button>
            )
          })}
        </div>
      </div>

      {/* Mapped Only Toggle */}
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
        <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-slate-700">
          <input
            type="checkbox"
            checked={onlyMapped}
            onChange={(e) => onOnlyMappedChange(e.target.checked)}
            className="w-4 h-4 rounded text-teal-600 focus:ring-teal-500/20 border-slate-300"
          />
          <span>Show facilities with interactive map coordinates only</span>
        </label>

        <span className="text-[11px] text-slate-400">
          OpenStreetMap Verified
        </span>
      </div>
    </div>
  )
}
