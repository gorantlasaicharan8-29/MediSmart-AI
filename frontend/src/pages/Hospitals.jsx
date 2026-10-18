import React from 'react'

export default function Hospitals() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Hospital Discovery</h1>
          <p className="text-sm text-slate-500">Interactive OpenStreetMap &amp; facility directory</p>
        </div>
        <div className="text-xs px-3 py-1.5 rounded-lg bg-teal-50 border border-teal-200 text-teal-800 font-medium">
          Phase 3 Deliverable • OpenStreetMap + Leaflet
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-2xl">
          🗺️
        </div>
        <h2 className="text-lg font-bold text-slate-900">Interactive Hospital Map Coming in Phase 3</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          The database schema for hospitals (including geographical latitude, longitude, and specialties arrays) is already created in PostgreSQL 18.6!
        </p>
      </div>
    </div>
  )
}
