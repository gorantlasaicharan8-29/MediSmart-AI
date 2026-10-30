import React from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import PatientQueueTracker from '../components/queue/PatientQueueTracker'
import WaitingRoomMonitor from '../components/queue/WaitingRoomMonitor'
import DoctorQueueConsole from '../components/queue/DoctorQueueConsole'
import MLStatusBadge from '../components/ml/MLStatusBadge'
import { Badge, ClinicalIcon } from '../components/ui'

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

  const isStaff = Boolean(user && ['doctor', 'hospital_admin', 'system_admin'].includes(user.role))

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-brand-border/80">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <Badge variant="teal" size="sm">
              <ClinicalIcon name="waiting-time" size={12} ariaHidden="true" />
              <span className="ml-1">Real-Time Clinic Queue</span>
            </Badge>
            <MLStatusBadge compact />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            Clinic Queue &amp; Waiting Room
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-1 max-w-2xl">
            Live digital queue token tracking, public waiting room displays, and clinical consultation management.
          </p>
        </div>

        {/* Tab Switcher & Fullscreen Kiosk TV Action */}
        <div className="flex flex-wrap items-center gap-3">
          <div
            role="tablist"
            aria-label="Queue views"
            className="inline-flex p-1 rounded-2xl bg-brand-ground border border-brand-border"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'tracker'}
              onClick={() => handleTabChange('tracker')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'tracker'
                  ? 'bg-brand-surface text-brand-text shadow-clinical-xs border border-brand-border/60'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              <ClinicalIcon name="ticket" size={14} ariaHidden="true" />
              <span>My Queue Token</span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'monitor'}
              onClick={() => handleTabChange('monitor')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'monitor'
                  ? 'bg-brand-deep text-white shadow-clinical-xs'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              <ClinicalIcon name="waiting-time" size={14} ariaHidden="true" />
              <span>Waiting Room Display</span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'doctor'}
              onClick={() => handleTabChange('doctor')}
              className={`px-3 sm:px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'doctor'
                  ? 'bg-brand-primary text-white shadow-clinical-xs'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              <ClinicalIcon name="stethoscope" size={14} ariaHidden="true" />
              <span>Doctor Console</span>
              {isStaff && (
                <span className="w-1.5 h-1.5 rounded-full bg-clinical-success animate-pulse" />
              )}
            </button>
          </div>

          <Link
            to="/queue/monitor"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-brand-text bg-brand-surface border border-brand-border hover:bg-brand-ground shadow-clinical-xs transition-all"
            title="Open Dedicated Full-Screen TV Kiosk"
          >
            <ClinicalIcon name="sparkles" size={13} ariaHidden="true" />
            <span>Kiosk TV Mode</span>
          </Link>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="transition-all duration-200">
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
