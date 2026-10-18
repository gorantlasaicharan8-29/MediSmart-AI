import React from 'react'

export default function HospitalCard({
  hospital,
  isSelected = false,
  onSelect = () => {},
  onViewDetails = () => {},
}) {
  const hasCoords = hospital.latitude !== null && hospital.longitude !== null

  return (
    <div
      onClick={() => onSelect(hospital)}
      className={`p-5 rounded-2xl border transition-all cursor-pointer bg-white ${
        isSelected
          ? 'border-teal-500 ring-2 ring-teal-500/20 shadow-md'
          : 'border-slate-200/90 hover:border-slate-300 hover:shadow-sm'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {/* Provenance Badge */}
            <span
              className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded-full border ${
                hospital.data_source === 'verified'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              {hospital.data_source === 'verified' ? 'Verified Partner' : 'Demonstration Data'}
            </span>

            {/* Coordinate Status */}
            <span
              className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
                hasCoords
                  ? 'bg-teal-50/70 text-teal-700 border-teal-200/70'
                  : 'bg-slate-100 text-slate-500 border-slate-200'
              }`}
            >
              {hasCoords ? '📍 GPS Mapped' : '⚠️ Location Pending'}
            </span>
          </div>

          <h3 className="text-base font-bold text-slate-900 group-hover:text-teal-600 transition-colors">
            {hospital.name}
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {hospital.address}, <span className="font-medium text-slate-700">{hospital.city}</span>, {hospital.state}
          </p>
        </div>
      </div>

      {/* Specialties */}
      {hospital.specialties && hospital.specialties.length > 0 && (
        <div className="mt-3.5 flex flex-wrap gap-1.5">
          {hospital.specialties.slice(0, 4).map((spec, idx) => (
            <span
              key={idx}
              className="text-[11px] font-medium px-2 py-0.5 rounded-lg bg-slate-50 text-slate-600 border border-slate-100"
            >
              {spec}
            </span>
          ))}
          {hospital.specialties.length > 4 && (
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-lg bg-slate-50 text-slate-400">
              +{hospital.specialties.length - 4} more
            </span>
          )}
        </div>
      )}

      {/* Contact & Actions */}
      <div className="mt-4 pt-3.5 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-2">
          {hospital.phone && (
            <span className="font-medium text-slate-700 flex items-center gap-1">
              📞 {hospital.phone}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {hasCoords && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                onSelect(hospital)
              }}
              className="text-slate-600 hover:text-teal-700 font-semibold px-2 py-1 rounded hover:bg-slate-50 transition-colors"
            >
              Pin on Map
            </button>
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onViewDetails(hospital)
            }}
            className="text-teal-600 hover:text-teal-700 font-semibold px-2.5 py-1 rounded-lg bg-teal-50 hover:bg-teal-100/70 transition-colors"
          >
            Details →
          </button>
        </div>
      </div>
    </div>
  )
}
