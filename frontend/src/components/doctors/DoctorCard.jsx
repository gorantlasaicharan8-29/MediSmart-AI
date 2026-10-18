import React from 'react'

export default function DoctorCard({ doctor, onBook }) {
  const user = doctor.user || {}
  const hospital = doctor.hospital || {}

  // Determine credential provenance badge
  const renderCredentialBadge = () => {
    switch (doctor.credential_status) {
      case 'verified':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <svg className="w-3.5 h-3.5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            Verified Specialist
          </span>
        )
      case 'sample':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
            <span>⚠️</span> Demo Profile
          </span>
        )
      case 'pending_verification':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <span>⏳</span> Verification Pending
          </span>
        )
    }
  }

  return (
    <div className="group relative flex flex-col justify-between bg-white rounded-2xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="space-y-4">
        {/* Top Header: Specialty & Credential Badge */}
        <div className="flex items-start justify-between gap-2">
          <span className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold bg-cyan-50 text-cyan-800 border border-cyan-100">
            {doctor.specialty}
          </span>
          {renderCredentialBadge()}
        </div>

        {/* Doctor Info */}
        <div>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-teal-500 to-cyan-500 text-white font-bold flex items-center justify-center text-lg shadow-sm">
              {user.full_name ? user.full_name.replace('Dr. ', '').charAt(0) : 'D'}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 group-hover:text-teal-700 transition-colors">
                {user.full_name || 'Medical Specialist'}
              </h3>
              <p className="text-xs text-slate-500 line-clamp-1">
                {doctor.qualification || 'Certified Medical Practitioner'}
              </p>
            </div>
          </div>
        </div>

        {/* Hospital Affiliation */}
        <div className="pt-2 border-t border-slate-100 space-y-1.5 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-teal-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
            <span className="font-medium text-slate-800 truncate">{hospital.name || 'Hospital Affiliation Pending'}</span>
          </div>
          {hospital.city && (
            <div className="flex items-center gap-2 text-slate-500 pl-6">
              <span>{hospital.city}, {hospital.state}</span>
            </div>
          )}
        </div>

        {/* Bio */}
        {doctor.bio && (
          <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed bg-slate-50/70 p-2.5 rounded-xl border border-slate-100">
            {doctor.bio}
          </p>
        )}

        {/* Clinical Stats */}
        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
          <div className="bg-slate-50 p-2 rounded-xl border border-slate-100">
            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Experience</span>
            <span className="font-bold text-slate-800">{doctor.experience_years} Years</span>
          </div>
          <div className="bg-slate-50 p-2 rounded-xl border border-slate-100">
            <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Consultation Fee</span>
            <span className="font-bold text-teal-700">₹{doctor.consultation_fee ? doctor.consultation_fee.toFixed(0) : 'Free'}</span>
          </div>
        </div>

        {/* Working Days */}
        {doctor.available_days && doctor.available_days.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider block">Clinic Days</span>
            <div className="flex flex-wrap gap-1">
              {doctor.available_days.map((day) => (
                <span key={day} className="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-medium">
                  {day.slice(0, 3)}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="pt-5 mt-4 border-t border-slate-100 flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-xs">
          <span className={`w-2 h-2 rounded-full ${doctor.is_available ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
          <span className={`font-medium ${doctor.is_available ? 'text-emerald-700' : 'text-slate-400'}`}>
            {doctor.is_available ? 'Available' : 'Unavailable'}
          </span>
        </div>

        <button
          type="button"
          disabled={!doctor.is_available}
          onClick={() => onBook(doctor)}
          className="inline-flex items-center justify-center px-4 py-2 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2"
        >
          Book Consultation
        </button>
      </div>
    </div>
  )
}
