import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getMyDoctorProfile } from '../../services/api'
import DoctorQueueConsole from '../../components/queue/DoctorQueueConsole'
import { Button, Badge, ClinicalIcon } from '../../components/ui'

export default function DoctorQueue() {
  const [doctorProfile, setDoctorProfile] = useState(null)

  useEffect(() => {
    getMyDoctorProfile()
      .then((data) => setDoctorProfile(data))
      .catch(() => {})
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fadeIn">
      {/* Header with TV Monitor Link */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="teal" size="sm">
              <ClinicalIcon name="activity" size={12} className="mr-1" />
              Live Clinical Console
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            Patient Consultation Queue
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-0.5">
            Call patients, manage consultation timers, add clinical notes, and coordinate room flow
          </p>
        </div>

        {doctorProfile?.id && (
          <div className="flex items-center gap-2">
            <Button
              as={Link}
              to={`/queue/monitor/${doctorProfile.id}`}
              target="_blank"
              rel="noopener noreferrer"
              variant="outline"
              size="sm"
              className="text-xs font-semibold"
            >
              <ClinicalIcon name="activity" size={14} className="mr-1.5" />
              Open Waiting Room TV Monitor &nearr;
            </Button>
          </div>
        )}
      </div>

      {/* Main Queue Console Component */}
      <DoctorQueueConsole initialDoctorId={doctorProfile?.id} />
    </div>
  )
}
