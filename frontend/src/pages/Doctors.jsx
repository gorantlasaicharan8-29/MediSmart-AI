import React, { useState, useEffect } from 'react'
import DoctorCard from '../components/doctors/DoctorCard'
import DoctorFilters from '../components/doctors/DoctorFilters'
import BookingModal from '../components/appointments/BookingModal'
import { getDoctors, getHospitals } from '../services/api'

export default function Doctors() {
  const [doctors, setDoctors] = useState([])
  const [hospitals, setHospitals] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDoctorForBooking, setSelectedDoctorForBooking] = useState(null)

  const [filters, setFilters] = useState({
    search: '',
    specialty: '',
    hospital_id: '',
    credential_status: '',
    available_only: false,
    page: 1,
    page_size: 24,
  })

  // Load hospitals once on mount for filter dropdown
  useEffect(() => {
    let ignore = false
    const fetchHospitals = async () => {
      try {
        const data = await getHospitals({ page_size: 100 })
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

  const [reloadKey, setReloadKey] = useState(0)
  const refreshDoctors = () => {
    setIsLoading(true)
    setReloadKey((k) => k + 1)
  }

  // Load doctors whenever filters change
  useEffect(() => {
    let ignore = false

    const fetchDoctors = async () => {
      try {
        const params = {
          page: filters.page,
          page_size: filters.page_size,
        }
        if (filters.search) params.search = filters.search
        if (filters.specialty) params.specialty = filters.specialty
        if (filters.hospital_id) params.hospital_id = filters.hospital_id
        if (filters.credential_status) params.credential_status = filters.credential_status
        if (filters.available_only) params.available_only = true

        const res = await getDoctors(params)
        if (!ignore) {
          setDoctors(res.items || [])
          setTotal(res.total || 0)
          setError(null)
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || 'Failed to load doctors')
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
  }, [filters, reloadKey])

  const handleFilterChange = (newFilters) => {
    setIsLoading(true)
    setFilters((prev) => ({
      ...prev,
      ...newFilters,
      page: 1,
    }))
  }

  const handleResetFilters = () => {
    setIsLoading(true)
    setFilters({
      search: '',
      specialty: '',
      hospital_id: '',
      credential_status: '',
      available_only: false,
      page: 1,
      page_size: 24,
    })
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-teal-50 text-teal-800 border border-teal-200 mb-2">
            <span>🩺</span> Specialist Directory &amp; Appointments
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
            Consult Verified Doctors &amp; Specialists
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl">
            Discover leading healthcare specialists across affiliated hospitals, check verified credentials, review consultation schedules, and book direct appointments with concurrency protection.
          </p>
        </div>

        <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 px-4 py-2.5 rounded-xl font-medium shrink-0">
          Showing <span className="font-bold text-slate-900">{doctors.length}</span> of{' '}
          <span className="font-bold text-slate-900">{total}</span> Specialists
        </div>
      </div>

      {/* Filter Bar */}
      <DoctorFilters
        filters={filters}
        onChange={handleFilterChange}
        onReset={handleResetFilters}
        hospitals={hospitals}
      />

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-sm text-rose-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={refreshDoctors}
            className="underline font-bold text-xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4 animate-pulse"
            >
              <div className="h-4 bg-slate-200 rounded w-1/3"></div>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-slate-200 rounded-xl"></div>
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-slate-200 rounded w-2/3"></div>
                  <div className="h-3 bg-slate-200 rounded w-1/2"></div>
                </div>
              </div>
              <div className="h-10 bg-slate-100 rounded-xl"></div>
              <div className="h-8 bg-slate-200 rounded-xl"></div>
            </div>
          ))}
        </div>
      ) : doctors.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center space-y-4 max-w-lg mx-auto shadow-sm">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-2xl">
            🔍
          </div>
          <h3 className="text-lg font-bold text-slate-900">No Specialists Found</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            We couldn't find any doctor matching your current filter criteria. Try clearing some filters or searching with different keywords.
          </p>
          <button
            type="button"
            onClick={handleResetFilters}
            className="px-4 py-2 text-xs font-bold text-teal-700 bg-teal-50 hover:bg-teal-100 rounded-xl border border-teal-200 transition-colors"
          >
            Reset All Filters
          </button>
        </div>
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
            // Refresh slots if modal reopens
          }}
        />
      )}
    </div>
  )
}
