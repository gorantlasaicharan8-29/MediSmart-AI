import React, { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import DoctorCard from '../components/doctors/DoctorCard'
import DoctorFilters from '../components/doctors/DoctorFilters'
import BookingModal from '../components/appointments/BookingModal'
import { getDoctors, getHospitals } from '../services/api'
import { Button, Badge, Skeleton, EmptyState, ClinicalIcon } from '../components/ui'

export default function Doctors() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [doctors, setDoctors] = useState([])
  const [hospitals, setHospitals] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDoctorForBooking, setSelectedDoctorForBooking] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  const [localFilters, setLocalFilters] = useState({
    credential_status: '',
    available_only: false,
    page: 1,
    page_size: 24,
  })

  // Synchronously derive effective query filters from URL search params & local state
  const effectiveFilters = {
    search: searchParams.get('search') || '',
    specialty: searchParams.get('specialty') || '',
    hospital_id: searchParams.get('hospital_id') || '',
    credential_status: localFilters.credential_status,
    available_only: localFilters.available_only,
    page: localFilters.page,
    page_size: localFilters.page_size,
  }

  // Load hospitals once on mount for filter dropdown

  useEffect(() => {
    let ignore = false
    const fetchHospitals = async () => {
      try {
        const data = await getHospitals({ limit: 100 })
        if (!ignore && data?.items) {
          setHospitals(data.items)
        }
      } catch {
        // Fallback gracefully if hospital loading fails
      }
    }
    fetchHospitals()
    return () => {
      ignore = true
    }
  }, [])

  const {
    search: querySearch,
    specialty: querySpecialty,
    hospital_id: queryHospitalId,
    credential_status,
    available_only,
    page,
    page_size,
  } = effectiveFilters

  // Load doctors whenever query filters change
  useEffect(() => {
    let ignore = false

    const fetchDoctors = async () => {
      setIsLoading(true)
      try {
        const params = {
          page,
          page_size,
        }
        if (querySearch) params.search = querySearch
        if (querySpecialty) params.specialty = querySpecialty
        if (queryHospitalId) params.hospital_id = queryHospitalId
        if (credential_status) params.credential_status = credential_status
        if (available_only) params.available_only = true

        const res = await getDoctors(params)
        if (!ignore) {
          setDoctors(res.items || [])
          setTotal(res.total || 0)
          setError(null)
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || 'Failed to load doctors directory.')
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    fetchDoctors()
    return () => {
      ignore = true
    }
  }, [
    querySearch,
    querySpecialty,
    queryHospitalId,
    credential_status,
    available_only,
    page,
    page_size,
    reloadKey,
  ])

  const handleFilterChange = (newFilters) => {
    const nextParams = new URLSearchParams(searchParams)
    let paramsChanged = false

    if ('search' in newFilters) {
      if (newFilters.search) nextParams.set('search', newFilters.search)
      else nextParams.delete('search')
      paramsChanged = true
    }
    if ('specialty' in newFilters) {
      if (newFilters.specialty) nextParams.set('specialty', newFilters.specialty)
      else nextParams.delete('specialty')
      paramsChanged = true
    }
    if ('hospital_id' in newFilters) {
      if (newFilters.hospital_id) nextParams.set('hospital_id', newFilters.hospital_id)
      else nextParams.delete('hospital_id')
      paramsChanged = true
    }

    if (paramsChanged) {
      setSearchParams(nextParams, { replace: true })
    }

    setLocalFilters((prev) => ({
      ...prev,
      ...newFilters,
      page: 1,
    }))
  }

  const handleResetFilters = () => {
    setLocalFilters({
      credential_status: '',
      available_only: false,
      page: 1,
      page_size: 24,
    })
    setSearchParams({}, { replace: true })
  }

  const refreshDoctors = () => {
    setReloadKey((k) => k + 1)
  }


  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-brand-border">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="teal" size="sm" dot>
              Specialist Directory
            </Badge>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-brand-text tracking-tight">
            Consult Verified Doctors &amp; Specialists
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-1 max-w-2xl leading-relaxed">
            Discover leading healthcare specialists across affiliated hospitals, review verified credentials and consultation fees, and schedule direct appointments.
          </p>
        </div>

        <div className="text-xs text-brand-muted bg-brand-surface border border-brand-border px-4 py-2.5 rounded-xl font-semibold shadow-clinical-xs shrink-0">
          Showing <span className="font-bold text-brand-text">{doctors.length}</span> of{' '}
          <span className="font-bold text-brand-primary">{total}</span> Active Profiles
        </div>
      </div>

      {/* Filter Bar */}
      <DoctorFilters
        filters={effectiveFilters}
        onChange={handleFilterChange}
        onReset={handleResetFilters}
        hospitals={hospitals}
      />


      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
            <span>{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refreshDoctors}
            className="text-xs font-bold"
          >
            Retry Search
          </Button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton.Card key={i} lines={3} />
          ))}
        </div>
      ) : doctors.length === 0 ? (
        /* Empty State */
        <EmptyState
          icon="stethoscope"
          title="No Specialists Found"
          description="We couldn't find any doctors matching your current filter criteria. Try clearing some filters or searching with different keywords."
          action={
            <Button
              variant="outline"
              size="md"
              onClick={handleResetFilters}
              className="text-xs font-semibold"
            >
              Reset All Filters
            </Button>
          }
        />
      ) : (
        /* Doctor Cards Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {doctors.map((doctor) => (
            <DoctorCard
              key={doctor.id}
              doctor={doctor}
              onBook={(doc) => setSelectedDoctorForBooking(doc)}
            />
          ))}
        </div>
      )}

      {/* Booking Modal */}
      {selectedDoctorForBooking && (
        <BookingModal
          doctor={selectedDoctorForBooking}
          onClose={() => setSelectedDoctorForBooking(null)}
          onSuccess={() => {
            // Success handler
          }}
        />
      )}
    </div>
  )
}
