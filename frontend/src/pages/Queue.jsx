import React from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import PatientQueueTracker from '../components/queue/PatientQueueTracker'
import WaitingRoomMonitor from '../components/queue/WaitingRoomMonitor'
import DoctorQueueConsole from '../components/queue/DoctorQueueConsole'

export default function Queue() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()

  // Derive active tab directly from URL query param or user role
  const tabParam = searchParams.get('tab')
  const activeTab = ['tracker', 'monitor', 'doctor'].includes(tabParam)
    ? tabParam
    : user?.role === 'doctor'
    ? 'doctor'
    : 'tracker'

  const handleTabChange = (tab) => {
    setSearchParams(tab === 'tracker' ? {} : { tab })
  }

  const isStaff = user && ['doctor', 'hospital_admin', 'system_admin'].includes(user.role)

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Live Clinic Queue &amp; Waiting Room
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time digital token tracking, public waiting room displays, and clinical consultation management.
          </p>
        </div>

        {/* Tab Switcher & Fullscreen Action */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex p-1 rounded-2xl bg-slate-100 border border-slate-200/80">
            <button
              type="button"
              onClick={() => handleTabChange('tracker')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'tracker'
                  ? 'bg-white text-slate-900 shadow-sm shadow-slate-200'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              🎟️ My Queue Token
            </button>
            <button
              type="button"
              onClick={() => handleTabChange('monitor')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                activeTab === 'monitor'
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              📺 Waiting Room Display
            </button>
            <button
              type="button"
              onClick={() => handleTabChange('doctor')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                activeTab === 'doctor'
                  ? 'bg-teal-600 text-white shadow-sm shadow-teal-700/20'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>🩺</span>
              <span>Doctor Console</span>
              {isStaff && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              )}
            </button>
          </div>

          <Link
            to="/queue/monitor"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 shadow-sm transition-all"
            title="Open Dedicated Full-Screen TV Kiosk"
          >
            <span>⛶</span> Kiosk TV Mode
          </Link>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="transition-all duration-300">
        {activeTab === 'tracker' && (
          <div className="space-y-6">
            <PatientQueueTracker />
          </div>
        )}
        {activeTab === 'monitor' && (
          <div className="space-y-6">
            <WaitingRoomMonitor />
          </div>
        )}
        {activeTab === 'doctor' && (
          <div className="space-y-6">
            <DoctorQueueConsole />
          </div>
        )}
      </div>
    </div>
  )
}
