import React from 'react'

export default function HospitalDetailModal({
  hospital,
  isOpen = false,
  onClose = () => {},
}) {
  if (!isOpen || !hospital) return null

  const hasCoords = hospital.latitude !== null && hospital.longitude !== null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="relative w-full max-w-xl bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-6 pb-4 border-b border-slate-100 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span
                className={`text-[10px] font-semibold tracking-wide uppercase px-2.5 py-0.5 rounded-full border ${
                  hospital.data_source === 'verified'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {hospital.data_source === 'verified' ? 'Verified Facility' : 'Demonstration Record'}
              </span>
              <span
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                  hasCoords
                    ? 'bg-teal-50 text-teal-700 border-teal-200'
                    : 'bg-slate-100 text-slate-500 border-slate-200'
                }`}
              >
                {hasCoords ? '📍 Geocoded' : '⚠️ Location Pending'}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900">{hospital.name}</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {hospital.address}, {hospital.city}, {hospital.state}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto text-sm">
          {/* Contact Information */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-slate-400 block font-medium">Telephone</span>
              <span className="font-semibold text-slate-800">
                {hospital.phone ? (
                  <a href={`tel:${hospital.phone}`} className="hover:text-teal-600">
                    {hospital.phone}
                  </a>
                ) : (
                  'Not specified'
                )}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Email Desk</span>
              <span className="font-semibold text-slate-800">
                {hospital.email ? (
                  <a href={`mailto:${hospital.email}`} className="hover:text-teal-600">
                    {hospital.email}
                  </a>
                ) : (
                  'Not specified'
                )}
              </span>
            </div>
          </div>

          {/* Clinical Specialties */}
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wide mb-2">
              Clinical Specialties
            </h3>
            {hospital.specialties && hospital.specialties.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {hospital.specialties.map((spec, i) => (
                  <span
                    key={i}
                    className="text-xs font-medium px-3 py-1 rounded-xl bg-teal-50 text-teal-800 border border-teal-200/60"
                  >
                    {spec}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No specialties listed.</p>
            )}
          </div>

          {/* Infrastructure & Facilities */}
          <div>
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wide mb-2">
              Facility Capabilities &amp; Infrastructure
            </h3>
            {hospital.facilities && hospital.facilities.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {hospital.facilities.map((fac, i) => (
                  <span
                    key={i}
                    className="text-xs font-medium px-3 py-1 rounded-xl bg-slate-100 text-slate-700 border border-slate-200/60"
                  >
                    ✓ {fac}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No facility attributes listed.</p>
            )}
          </div>

          {/* Coordinates & Provenance Box */}
          <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/60 text-xs space-y-1.5">
            <div className="flex items-center justify-between text-slate-500">
              <span>Geographic Coordinates</span>
              <span className="font-mono font-medium text-slate-800">
                {hasCoords
                  ? `${hospital.latitude.toFixed(4)}° N, ${hospital.longitude.toFixed(4)}° E`
                  : 'Pending GPS Survey'}
              </span>
            </div>
            <div className="flex items-center justify-between text-slate-500 pt-1 border-t border-slate-200/50">
              <span>Data Attribution</span>
              <span className="text-[11px] font-medium text-slate-700">
                {hospital.source_attribution || 'MediSmart Verified Records'}
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <p className="text-[11px] text-slate-400">
            Map data provided under OpenStreetMap terms.
          </p>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
