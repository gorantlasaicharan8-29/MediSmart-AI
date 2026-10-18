import React from 'react'

export default function Queue() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Real-Time Queue Management</h1>
          <p className="text-sm text-slate-500">Digital token tracking and WebSocket live updates</p>
        </div>
        <div className="text-xs px-3 py-1.5 rounded-lg bg-teal-50 border border-teal-200 text-teal-800 font-medium">
          Phase 5 Deliverable • WebSockets &amp; Live Tracking
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center space-y-4">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto text-2xl">
          ⏱️
        </div>
        <h2 className="text-lg font-bold text-slate-900">Live WebSocket Queue Updates Coming in Phase 5</h2>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          The `queue_entries` database model with real-time status tracking, token positions, and wait-time estimations is already migrated in PostgreSQL!
        </p>
      </div>
    </div>
  )
}
