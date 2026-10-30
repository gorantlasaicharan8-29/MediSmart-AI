import React, { useState, useEffect } from 'react'
import { getMyDoctorProfile } from '../../services/api'
import DoctorScheduleCalendar from '../../components/doctor/DoctorScheduleCalendar'
import { Skeleton } from '../../components/ui'

export default function DoctorSchedule() {
  const [doctorProfile, setDoctorProfile] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    getMyDoctorProfile()
      .then((data) => setDoctorProfile(data))
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fadeIn">
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-10 w-64 rounded-xl" />
          <Skeleton className="h-64 w-full rounded-3xl" />
        </div>
      ) : (
        <DoctorScheduleCalendar
          doctorId={doctorProfile?.id}
          doctorProfile={doctorProfile}
        />
      )}
    </div>
  )
}
