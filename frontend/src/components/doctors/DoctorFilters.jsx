import React from 'react'

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
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
      {/* Top Search Bar */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          value={filters.search}
          onChange={(e) => onChange({ search: e.target.value })}
          placeholder="Search by doctor name, specialty, qualification, or hospital..."
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50/50 text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
        />
        {filters.search && (
          <button
            type="button"
            onClick={() => onChange({ search: '' })}
            className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-xs text-slate-400 hover:text-slate-600"
          >
            Clear
          </button>
        )}
      </div>

      {/* Filter Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Specialty Select */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Specialty</label>
          <select
            value={filters.specialty}
            onChange={(e) => onChange({ specialty: e.target.value })}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
          >
            <option value="">All Specialties</option>
            {SPECIALTIES.map((spec) => (
              <option key={spec} value={spec}>
                {spec}
              </option>
            ))}
          </select>
        </div>

        {/* Hospital Affiliation Select */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Hospital Affiliation</label>
          <select
            value={filters.hospital_id}
            onChange={(e) => onChange({ hospital_id: e.target.value })}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all truncate"
          >
            <option value="">All Hospitals</option>
            {hospitals.map((hosp) => (
              <option key={hosp.id} value={hosp.id}>
                {hosp.name} ({hosp.city})
              </option>
            ))}
          </select>
        </div>

        {/* Credential Status Select */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">Credential Status</label>
          <select
            value={filters.credential_status}
            onChange={(e) => onChange({ credential_status: e.target.value })}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
          >
            <option value="">All Profiles</option>
            <option value="verified">Verified Specialists Only</option>
            <option value="sample">Demonstration Profiles</option>
            <option value="pending_verification">Pending Verification</option>
          </select>
        </div>

        {/* Available Only & Reset */}
        <div className="flex items-end justify-between gap-2">
          <label className="flex items-center gap-2 cursor-pointer select-none py-2">
            <input
              type="checkbox"
              checked={filters.available_only}
              onChange={(e) => onChange({ available_only: e.target.checked })}
              className="w-4 h-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500 cursor-pointer"
            />
            <span className="text-xs font-medium text-slate-700">Available Today</span>
          </label>

          <button
            type="button"
            onClick={onReset}
            className="text-xs text-slate-500 hover:text-teal-700 font-semibold py-2 px-2 transition-colors"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  )
}
