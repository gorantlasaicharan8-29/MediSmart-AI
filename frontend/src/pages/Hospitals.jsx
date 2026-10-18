import React, { useState, useEffect, useMemo } from 'react'
import { getHospitals } from '../services/api'
import { useAuth } from '../context/useAuth'
import HospitalMap from '../components/map/HospitalMap'
import HospitalCard from '../components/hospitals/HospitalCard'
import HospitalFilters from '../components/hospitals/HospitalFilters'
import HospitalDetailModal from '../components/hospitals/HospitalDetailModal'
import CreateHospitalModal from '../components/hospitals/CreateHospitalModal'

export default function Hospitals() {
  const { user } = useAuth()
  const canManageHospitals = user && (user.role === 'hospital_admin' || user.role === 'system_admin')

  const [hospitals, setHospitals] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Filters State
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedCity, setSelectedCity] = useState('')
  const [selectedSpecialty, setSelectedSpecialty] = useState('')
  const [onlyMapped, setOnlyMapped] = useState(false)

  // Selection & Modal States
  const [selectedHospital, setSelectedHospital] = useState(null)
  const [detailHospital, setDetailHospital] = useState(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [mobileView, setMobileView] = useState('list') // 'list' | 'map'

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
    }, 350)
    return () => clearTimeout(timer)
  }, [search])

  // Fetch hospitals from API with cancellation
  useEffect(() => {
    let ignore = false

    const loadHospitals = async () => {
      try {
        const params = {
          limit: 100,
          offset: 0,
        }
        if (debouncedSearch) params.search = debouncedSearch
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
  }, [debouncedSearch, selectedCity, selectedSpecialty, onlyMapped, refreshTrigger])

  // Compute unique cities for the dropdown
  const uniqueCities = useMemo(() => {
    const citySet = new Set(hospitals.map((h) => h.city).filter(Boolean))
    return Array.from(citySet).sort()
  }, [hospitals])

  const mappedCount = useMemo(() => {
    return hospitals.filter((h) => h.latitude !== null && h.longitude !== null).length
  }, [hospitals])

  const unmappedCount = hospitals.length - mappedCount

  const handleResetFilters = () => {
    setSearch('')
    setDebouncedSearch('')
    setSelectedCity('')
    setSelectedSpecialty('')
    setOnlyMapped(false)
  }

  const handleHospitalCreated = (newHospital) => {
    setRefreshTrigger((prev) => prev + 1)
    setSelectedHospital(newHospital)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Hospital Discovery</h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-teal-50 border border-teal-200 text-teal-800 font-semibold">
              Live Directory
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Explore verified healthcare centers and clinical specialties on OpenStreetMap
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick Metrics */}
          <div className="hidden lg:flex items-center gap-2 text-xs font-medium text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-2xs">
            <span>{totalCount} Total Facilities</span>
            <span className="text-slate-300">•</span>
            <span className="text-teal-600 font-semibold">{mappedCount} GPS Mapped</span>
          </div>

          {/* Admin Facility Button */}
          {canManageHospitals && (
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors"
            >
              <span>+</span>
              <span>Add Facility</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Component */}
      <HospitalFilters
        search={search}
        onSearchChange={setSearch}
        selectedCity={selectedCity}
        onCityChange={setSelectedCity}
        selectedSpecialty={selectedSpecialty}
        onSpecialtyChange={setSelectedSpecialty}
        onlyMapped={onlyMapped}
        onOnlyMappedChange={setOnlyMapped}
        cities={uniqueCities}
        onReset={handleResetFilters}
      />

      {/* Mobile View Toggle Switcher */}
      <div className="flex md:hidden bg-slate-100 p-1 rounded-xl">
        <button
          type="button"
          onClick={() => setMobileView('list')}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
            mobileView === 'list'
              ? 'bg-white text-slate-900 shadow-2xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Directory List ({hospitals.length})
        </button>
        <button
          type="button"
          onClick={() => setMobileView('map')}
          className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
            mobileView === 'map'
              ? 'bg-white text-slate-900 shadow-2xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Interactive Map ({mappedCount})
        </button>
      </div>

      {/* Error Message */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
          ⚠️ {errorMessage}
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
            <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200/80 text-[11px] text-amber-800 flex items-start gap-2.5">
              <span className="text-amber-600 font-bold">ℹ</span>
              <div>
                <span className="font-semibold">{unmappedCount} facility</span> listed without physical coordinates. These facilities appear in the list directory with contact details.
              </div>
            </div>
          )}

          {isLoading ? (
            <div className="p-12 text-center space-y-3 bg-white rounded-2xl border border-slate-200">
              <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-xs text-slate-500 font-medium">Loading hospital directory...</p>
            </div>
          ) : hospitals.length === 0 ? (
            <div className="p-10 text-center space-y-3 bg-white rounded-2xl border border-slate-200">
              <div className="w-12 h-12 rounded-xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto text-xl font-bold">
                🏥
              </div>
              <h3 className="text-sm font-bold text-slate-800">No Hospitals Found</h3>
              <p className="text-xs text-slate-500 max-w-xs mx-auto">
                No healthcare centers matched your selected filters or search terms.
              </p>
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs font-semibold text-teal-600 hover:underline pt-2"
              >
                Reset All Filters
              </button>
            </div>
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
          className={`md:col-span-6 lg:col-span-7 sticky top-20 h-[520px] sm:h-[620px] ${
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
