import React, { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getHospitals } from '../services/api'
import { useAuth } from '../context/useAuth'
import HospitalMap from '../components/map/HospitalMap'
import HospitalCard from '../components/hospitals/HospitalCard'
import HospitalFilters from '../components/hospitals/HospitalFilters'
import HospitalDetailModal from '../components/hospitals/HospitalDetailModal'
import CreateHospitalModal from '../components/hospitals/CreateHospitalModal'
import { Button, Badge, Skeleton, EmptyState, ClinicalIcon } from '../components/ui'

export default function Hospitals() {
  const { user } = useAuth()
  const canManageHospitals =
    user && (user.role === 'hospital_admin' || user.role === 'system_admin')
  const [searchParams, setSearchParams] = useSearchParams()

  const urlSearch = searchParams.get('search') || ''
  const selectedCity = searchParams.get('city') || ''
  const selectedSpecialty = searchParams.get('specialty') || ''

  const [hospitals, setHospitals] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Local search text input (debounces into searchParams)
  const [searchInput, setSearchInput] = useState(urlSearch)
  const [onlyMapped, setOnlyMapped] = useState(false)

  // Selection & Modal States
  const [selectedHospital, setSelectedHospital] = useState(null)
  const [detailHospital, setDetailHospital] = useState(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [mobileView, setMobileView] = useState('list') // 'list' | 'map'

  // Debounce search input to URL query parameters
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (searchInput.trim()) {
          next.set('search', searchInput.trim())
        } else {
          next.delete('search')
        }
        return next
      }, { replace: true })
    }, 350)
    return () => clearTimeout(timer)
  }, [searchInput, setSearchParams])

  // Fetch hospitals from API
  useEffect(() => {
    let ignore = false

    const loadHospitals = async () => {
      setIsLoading(true)
      try {
        const params = {
          limit: 100,
          offset: 0,
        }
        if (urlSearch) params.search = urlSearch
        if (selectedCity) params.city = selectedCity
        if (selectedSpecialty) params.specialty = selectedSpecialty
        if (onlyMapped) params.has_coords = true

        const res = await getHospitals(params)
        if (!ignore) {
          setHospitals(res.items || [])
          setTotalCount(res.total || 0)
          setErrorMessage(null)
          setSelectedHospital((prev) =>
            prev && !res.items.some((h) => h.id === prev.id) ? null : prev
          )
        }
      } catch (err) {
        if (!ignore) {
          setErrorMessage(err.message || 'Failed to load hospital facilities.')
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    loadHospitals()
    return () => {
      ignore = true
    }
  }, [urlSearch, selectedCity, selectedSpecialty, onlyMapped, refreshTrigger])

  // Compute unique cities for dropdown
  const uniqueCities = useMemo(() => {
    const citySet = new Set(hospitals.map((h) => h.city).filter(Boolean))
    return Array.from(citySet).sort()
  }, [hospitals])

  const mappedCount = useMemo(() => {
    return hospitals.filter((h) => h.latitude !== null && h.longitude !== null).length
  }, [hospitals])

  const unmappedCount = hospitals.length - mappedCount

  const handleCityChange = (city) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (city) next.set('city', city)
      else next.delete('city')
      return next
    }, { replace: true })
  }

  const handleSpecialtyChange = (spec) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (spec) next.set('specialty', spec)
      else next.delete('specialty')
      return next
    }, { replace: true })
  }

  const handleResetFilters = () => {
    setSearchInput('')
    setOnlyMapped(false)
    setSearchParams({}, { replace: true })
  }


  const handleHospitalCreated = (newHospital) => {
    setRefreshTrigger((prev) => prev + 1)
    setSelectedHospital(newHospital)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-brand-border">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
              Hospital Discovery
            </h1>
            <Badge variant="teal" size="sm" dot>
              Live Directory
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-brand-muted mt-1">
            Explore verified healthcare centers and clinical specialties on OpenStreetMap
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick Metrics */}
          <div className="hidden lg:flex items-center gap-2.5 text-xs font-semibold text-brand-muted bg-brand-surface border border-brand-border px-3.5 py-2 rounded-xl shadow-clinical-xs">
            <span>{totalCount} Total Facilities</span>
            <span className="text-brand-border">&bull;</span>
            <span className="text-brand-accent">{mappedCount} GPS Geocoded</span>
          </div>

          {/* Admin Facility Button */}
          {canManageHospitals && (
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsCreateOpen(true)}
              leftIcon={<ClinicalIcon name="hospital" size={16} ariaHidden="true" />}
              className="text-xs font-semibold"
            >
              Add Hospital Facility
            </Button>
          )}
        </div>
      </div>

      {/* Filter Component */}
      <HospitalFilters
        search={searchInput}
        onSearchChange={setSearchInput}
        selectedCity={selectedCity}
        onCityChange={handleCityChange}
        selectedSpecialty={selectedSpecialty}
        onSpecialtyChange={handleSpecialtyChange}
        onlyMapped={onlyMapped}
        onOnlyMappedChange={setOnlyMapped}
        cities={uniqueCities}
        onReset={handleResetFilters}
      />


      {/* Mobile View Toggle Switcher */}
      <div className="flex md:hidden bg-brand-ground p-1 rounded-xl border border-brand-border">
        <button
          type="button"
          onClick={() => setMobileView('list')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
            mobileView === 'list'
              ? 'bg-brand-surface text-brand-deep shadow-clinical-xs'
              : 'text-brand-muted hover:text-brand-text'
          }`}
        >
          Directory List ({hospitals.length})
        </button>
        <button
          type="button"
          onClick={() => setMobileView('map')}
          className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
            mobileView === 'map'
              ? 'bg-brand-surface text-brand-deep shadow-clinical-xs'
              : 'text-brand-muted hover:text-brand-text'
          }`}
        >
          Interactive Map ({mappedCount})
        </button>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
            <span>{errorMessage}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRefreshTrigger((prev) => prev + 1)}
            className="text-xs font-bold"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Main Split Layout: Directory Cards (Left) + Interactive Leaflet Map (Right) */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
        {/* Left Column: Hospital Cards */}
        <div
          className={`md:col-span-6 lg:col-span-5 space-y-3.5 ${
            mobileView === 'map' ? 'hidden md:block' : 'block'
          }`}
        >
          {/* Missing Location Callout */}
          {unmappedCount > 0 && !onlyMapped && (
            <div className="p-3.5 rounded-xl bg-brand-ground border border-brand-border text-[11px] text-brand-muted flex items-start gap-2.5">
              <ClinicalIcon
                name="info"
                size={14}
                className="text-brand-accent shrink-0 mt-0.5"
                ariaHidden="true"
              />
              <div>
                <span className="font-bold text-brand-text">{unmappedCount} facility</span> listed with contact information prior to GPS coordinates completion.
              </div>
            </div>
          )}

          {isLoading ? (
            <div className="space-y-3.5">
              <Skeleton.Card lines={2} />
              <Skeleton.Card lines={2} />
              <Skeleton.Card lines={2} />
            </div>
          ) : hospitals.length === 0 ? (
            <EmptyState
              icon="hospital"
              title="No Hospitals Found"
              description="No healthcare centers matched your selected filters or search terms. Try resetting your search or selecting another city."
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
            hospitals.map((hospital) => (
              <HospitalCard
                key={hospital.id}
                hospital={hospital}
                isSelected={selectedHospital?.id === hospital.id}
                onSelect={(h) => {
                  setSelectedHospital(h)
                  if (mobileView === 'list') {
                    setMobileView('map')
                  }
                }}
                onViewDetails={(h) => setDetailHospital(h)}
              />
            ))
          )}
        </div>

        {/* Right Column: Interactive Leaflet Map (Sticky on Desktop) */}
        <div
          className={`md:col-span-6 lg:col-span-7 sticky top-20 h-[480px] sm:h-[580px] md:h-[640px] ${
            mobileView === 'list' ? 'hidden md:block' : 'block'
          }`}
        >
          <HospitalMap
            hospitals={hospitals}
            selectedHospital={selectedHospital}
            onSelectHospital={setSelectedHospital}
            onOpenDetails={(h) => setDetailHospital(h)}
          />
        </div>
      </div>

      {/* Modals */}
      <HospitalDetailModal
        hospital={detailHospital}
        isOpen={Boolean(detailHospital)}
        onClose={() => setDetailHospital(null)}
      />

      <CreateHospitalModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={handleHospitalCreated}
      />
    </div>
  )
}
