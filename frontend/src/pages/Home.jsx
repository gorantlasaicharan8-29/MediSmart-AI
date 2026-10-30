import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { checkBackendHealth, checkDatabaseHealth } from '../services/api'
import { Button, Badge, ClinicalIcon } from '../components/ui'

const QUICK_SPECIALTIES = [
  'Cardiology',
  'Pediatrics',
  'Orthopedics',
  'General Medicine',
  'Dermatology',
  'Neurology',
]

export default function Home() {
  const navigate = useNavigate()
  const [healthStatus, setHealthStatus] = useState({
    backend: 'checking...',
    database: 'checking...',
    checked: false,
  })

  // Search State
  const [searchQuery, setSearchQuery] = useState('')
  const [searchType, setSearchType] = useState('hospitals') // 'hospitals' | 'doctors'

  useEffect(() => {
    let ignore = false
    async function loadHealth() {
      try {
        const [backend, db] = await Promise.all([
          checkBackendHealth(),
          checkDatabaseHealth(),
        ])
        if (!ignore) {
          setHealthStatus({
            backend: backend?.status === 'ok' ? 'Online' : 'Offline',
            database:
              db?.status === 'ok' && db?.database === 'connected'
                ? 'Online'
                : 'Offline',
            checked: true,
          })
        }
      } catch {
        if (!ignore) {
          setHealthStatus({
            backend: 'Offline',
            database: 'Offline',
            checked: true,
          })
        }
      }
    }
    loadHealth()
    return () => {
      ignore = true
    }
  }, [])

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    const trimmed = searchQuery.trim()
    const targetPath = searchType === 'doctors' ? '/doctors' : '/hospitals'
    if (trimmed) {
      navigate(`${targetPath}?search=${encodeURIComponent(trimmed)}`)
    } else {
      navigate(targetPath)
    }
  }

  const isDbOnline = healthStatus.database === 'Online'

  return (
    <div className="space-y-16 py-8 md:py-14">
      {/* 1. Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Hero Copy */}
          <div className="lg:col-span-7 space-y-6">
            <div className="flex flex-wrap items-center gap-2.5">
              <Badge variant="teal" size="md" dot>
                MediSmart Healthcare Platform
              </Badge>
              <Badge
                variant={isDbOnline ? 'success' : 'warning'}
                size="md"
                dot
                pulseDot={isDbOnline}
              >
                Services: {healthStatus.backend} &bull; Database:{' '}
                {healthStatus.database}
              </Badge>
            </div>

            <div className="space-y-3">
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-brand-text tracking-tight leading-[1.15]">
                Smart Hospital Discovery, Specialist Consultations, &amp;{' '}
                <span className="text-brand-accent">Live Queue Visibility</span>
              </h1>
              <p className="text-sm sm:text-base text-brand-muted leading-relaxed max-w-2xl">
                Coordinate clinic visits with complete certainty. Discover verified healthcare facilities, schedule conflict-free doctor consultations, and track real-time queue tokens without sitting in crowded waiting halls.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button
                as={Link}
                to="/hospitals"
                variant="primary"
                size="lg"
                leftIcon={<ClinicalIcon name="hospital" size={18} ariaHidden="true" />}
              >
                Find Hospitals
              </Button>
              <Button
                as={Link}
                to="/doctors"
                variant="outline"
                size="lg"
                leftIcon={<ClinicalIcon name="stethoscope" size={18} ariaHidden="true" />}
              >
                Specialist Directory
              </Button>
              <Button
                as={Link}
                to="/queue"
                variant="secondary"
                size="lg"
                leftIcon={<ClinicalIcon name="clock" size={18} ariaHidden="true" />}
              >
                Live Queue
              </Button>
            </div>

            {/* Micro Feature Indicators */}
            <div className="pt-3 border-t border-brand-border/70 flex flex-wrap items-center gap-5 text-xs text-brand-muted font-medium">
              <div className="flex items-center gap-1.5">
                <ClinicalIcon
                  name="check-circle"
                  size={16}
                  className="text-brand-accent"
                  ariaHidden="true"
                />
                <span>Interactive OpenStreetMap</span>
              </div>
              <div className="flex items-center gap-1.5">
                <ClinicalIcon
                  name="check-circle"
                  size={16}
                  className="text-brand-accent"
                  ariaHidden="true"
                />
                <span>Real-Time WebSocket Tokens</span>
              </div>
              <div className="flex items-center gap-1.5">
                <ClinicalIcon
                  name="check-circle"
                  size={16}
                  className="text-brand-accent"
                  ariaHidden="true"
                />
                <span>Zero Patient PII in Queue Displays</span>
              </div>
            </div>
          </div>

          {/* Hero Visual Card: Live Queue Simulation Preview */}
          <div className="lg:col-span-5">
            <div className="bg-brand-surface rounded-2xl border border-brand-border p-6 shadow-clinical-md space-y-5">
              <div className="flex items-center justify-between pb-3.5 border-b border-brand-border/80">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-brand-mint text-brand-deep flex items-center justify-center font-bold text-xs shadow-clinical-xs">
                    <ClinicalIcon name="clock" size={16} ariaHidden="true" />
                  </div>
                  <div>
                    <h2 className="text-xs font-bold text-brand-text leading-tight">
                      Live Queue Monitor Preview
                    </h2>
                    <p className="text-[11px] text-brand-muted">
                      City General Hospital &bull; Cardiology
                    </p>
                  </div>
                </div>
                <Badge variant="success" size="sm" dot pulseDot>
                  Active Session
                </Badge>
              </div>

              {/* Simulated Queue Screen */}
              <div className="rounded-xl bg-brand-deep text-white p-5 space-y-3.5 shadow-clinical-sm">
                <div className="flex justify-between items-start">
                  <span className="text-[11px] uppercase tracking-wider text-teal-200/80 font-bold">
                    Now In Consultation
                  </span>
                  <span className="text-xs font-bold text-teal-300">
                    Room 304
                  </span>
                </div>
                <div className="flex items-baseline justify-between">
                  <div>
                    <div className="text-3xl sm:text-4xl font-extrabold tracking-tight">
                      Token #42
                    </div>
                    <div className="text-xs text-teal-100/70 pt-0.5">
                      Your Sample Ticket: <span className="font-bold text-white">#45</span>
                    </div>
                  </div>
                  <Badge variant="mint" size="sm">
                    Est. Wait: ~14 mins
                  </Badge>
                </div>
                <div className="pt-2 border-t border-teal-800/80 flex items-center justify-between text-xs text-teal-100/90 font-medium">
                  <span>Patients Ahead: <strong className="text-white">2</strong></span>
                  <span>Dr. Sarah Mitchell, MD</span>
                </div>
              </div>

              {/* Simulation Note & Action */}
              <div className="space-y-3">
                <div className="p-2.5 rounded-xl bg-brand-ground border border-brand-border text-[11px] text-brand-muted flex items-start gap-2">
                  <ClinicalIcon
                    name="info"
                    size={14}
                    className="text-brand-accent shrink-0 mt-0.5"
                    ariaHidden="true"
                  />
                  <span>
                    <strong>Simulated demonstration:</strong> Real patient identifiers are never displayed. When logged in, your active appointments provide direct queue tickets.
                  </span>
                </div>

                <Button
                  as={Link}
                  to="/queue"
                  variant="outline"
                  size="md"
                  className="w-full text-xs font-semibold justify-center"
                >
                  View Live Public Queue
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Functional Discovery Search Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-6 sm:p-8 shadow-clinical-sm space-y-5">
          <div className="max-w-2xl space-y-1">
            <h2 className="text-xl sm:text-2xl font-bold text-brand-text tracking-tight">
              Direct Clinical Search
            </h2>
            <p className="text-xs sm:text-sm text-brand-muted">
              Search verified medical centers, departments, or clinical specialists by name or specialty.
            </p>
          </div>

          {/* Form */}
          <form
            onSubmit={handleSearchSubmit}
            className="flex flex-col md:flex-row gap-3"
            role="search"
            aria-label="Clinical Discovery Search"
          >
            {/* Scope Selector */}
            <div className="w-full md:w-44 shrink-0">
              <label htmlFor="search-scope" className="sr-only">
                Search Category
              </label>
              <select
                id="search-scope"
                value={searchType}
                onChange={(e) => setSearchType(e.target.value)}
                className="w-full h-11 px-3.5 bg-brand-ground text-brand-text text-xs font-semibold rounded-xl border border-brand-border focus:outline-none focus:ring-2 focus:ring-brand-accent cursor-pointer"
              >
                <option value="hospitals">Hospitals &amp; Clinics</option>
                <option value="doctors">Doctors &amp; Specialists</option>
              </select>
            </div>

            {/* Search Input */}
            <div className="relative flex-1">
              <label htmlFor="search-query" className="sr-only">
                Search query
              </label>
              <div
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-brand-muted pointer-events-none"
                aria-hidden="true"
              >
                <ClinicalIcon name="search" size={18} />
              </div>
              <input
                id="search-query"
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={
                  searchType === 'doctors'
                    ? 'Search doctor by name, qualification, or specialty...'
                    : 'Search hospital by facility name, city, or specialty...'
                }
                className="w-full h-11 pl-10 pr-4 bg-brand-ground text-brand-text placeholder:text-brand-muted/70 text-sm rounded-xl border border-brand-border focus:outline-none focus:ring-2 focus:ring-brand-accent transition-all"
              />
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              size="md"
              className="h-11 px-6 text-sm font-semibold shrink-0"
              leftIcon={<ClinicalIcon name="search" size={16} ariaHidden="true" />}
            >
              Search {searchType === 'doctors' ? 'Doctors' : 'Hospitals'}
            </Button>
          </form>

          {/* Quick Specialties Pills */}
          <div className="pt-1 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-brand-muted font-medium mr-1">
              Popular Specialties:
            </span>
            {QUICK_SPECIALTIES.map((spec) => (
              <button
                key={spec}
                type="button"
                onClick={() =>
                  navigate(`/doctors?specialty=${encodeURIComponent(spec)}`)
                }
                className="px-2.5 py-1 rounded-lg bg-brand-ground hover:bg-brand-mint text-brand-text hover:text-brand-deep border border-brand-border/80 text-xs font-medium transition-colors cursor-pointer"
              >
                {spec}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* 3. Core Feature Pillars Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-10 space-y-2">
          <Badge variant="teal" size="sm">
            Core Capabilities
          </Badge>
          <h2 className="text-2xl sm:text-3xl font-bold text-brand-text tracking-tight">
            Integrated Operations for Modern Healthcare
          </h2>
          <p className="text-xs sm:text-sm text-brand-muted leading-relaxed">
            Every feature connects clinical discovery with operational queue efficiency, ensuring patients and providers stay synchronized.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Pillar 1: Hospital Discovery */}
          <div className="p-6 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs hover:shadow-clinical-sm transition-all space-y-3.5">
            <div className="w-10 h-10 rounded-xl bg-teal-50 text-brand-primary flex items-center justify-center border border-teal-100 shadow-clinical-xs">
              <ClinicalIcon name="hospital" size={20} ariaHidden="true" />
            </div>
            <h3 className="font-bold text-brand-text text-base">
              Facility Discovery &amp; Maps
            </h3>
            <p className="text-xs text-brand-muted leading-relaxed">
              Explore medical centers using Leaflet and OpenStreetMap integration. Filter by city, specialty, and live bed occupancy without third-party tracking.
            </p>
            <Link
              to="/hospitals"
              className="inline-flex items-center gap-1 text-xs font-bold text-brand-accent hover:text-brand-deep hover:underline pt-1"
            >
              <span>Explore Facilities</span>
              <ClinicalIcon name="arrow-right" size={13} ariaHidden="true" />
            </Link>
          </div>

          {/* Pillar 2: Doctor Specialists */}
          <div className="p-6 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs hover:shadow-clinical-sm transition-all space-y-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center border border-blue-100 shadow-clinical-xs">
              <ClinicalIcon name="stethoscope" size={20} ariaHidden="true" />
            </div>
            <h3 className="font-bold text-brand-text text-base">
              Specialist Consultations
            </h3>
            <p className="text-xs text-brand-muted leading-relaxed">
              View verified doctor credentials, consultation fees, and schedule slot-based appointments with immediate backend conflict validation.
            </p>
            <Link
              to="/doctors"
              className="inline-flex items-center gap-1 text-xs font-bold text-brand-accent hover:text-brand-deep hover:underline pt-1"
            >
              <span>Find Specialists</span>
              <ClinicalIcon name="arrow-right" size={13} ariaHidden="true" />
            </Link>
          </div>

          {/* Pillar 3: Real-Time Queue */}
          <div className="p-6 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs hover:shadow-clinical-sm transition-all space-y-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-100 shadow-clinical-xs">
              <ClinicalIcon name="clock" size={20} ariaHidden="true" />
            </div>
            <h3 className="font-bold text-brand-text text-base">
              Digital Queue Coordination
            </h3>
            <p className="text-xs text-brand-muted leading-relaxed">
              Follow appointment ticket positions through live WebSocket updates. Arrive only when your turn approaches, minimizing crowded waiting rooms.
            </p>
            <Link
              to="/queue"
              className="inline-flex items-center gap-1 text-xs font-bold text-brand-accent hover:text-brand-deep hover:underline pt-1"
            >
              <span>View Public Queue</span>
              <ClinicalIcon name="arrow-right" size={13} ariaHidden="true" />
            </Link>
          </div>

          {/* Pillar 4: Predictive Intelligence */}
          <div className="p-6 rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-xs hover:shadow-clinical-sm transition-all space-y-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-800 flex items-center justify-center border border-amber-200/80 shadow-clinical-xs">
              <ClinicalIcon name="heart-pulse" size={20} ariaHidden="true" />
            </div>
            <h3 className="font-bold text-brand-text text-base">
              Wait-Time Forecasting
            </h3>
            <p className="text-xs text-brand-muted leading-relaxed">
              Machine learning models forecast dynamic waiting duration and calculate attendance predictability to help clinics balance patient queues.
            </p>
            <div className="text-[11px] font-semibold text-brand-muted pt-1">
              XGBoost &bull; Logistic Reg
            </div>
          </div>
        </div>
      </section>

      {/* 4. How It Works Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-brand-surface rounded-2xl border border-brand-border p-6 sm:p-10 shadow-clinical-sm space-y-8">
          <div className="text-center max-w-xl mx-auto space-y-1.5">
            <h2 className="text-xl sm:text-2xl font-bold text-brand-text tracking-tight">
              Patient Journey: Four Simple Steps
            </h2>
            <p className="text-xs sm:text-sm text-brand-muted">
              From discovering the right facility to completing your consultation.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="space-y-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep font-bold text-xs flex items-center justify-center shadow-xs">
                1
              </div>
              <h3 className="font-bold text-brand-text text-sm">
                Discover &amp; Select
              </h3>
              <p className="text-xs text-brand-muted leading-relaxed">
                Filter hospitals by city and specialty, or explore qualified doctors by department.
              </p>
            </div>

            <div className="space-y-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep font-bold text-xs flex items-center justify-center shadow-xs">
                2
              </div>
              <h3 className="font-bold text-brand-text text-sm">
                Reserve Appointment
              </h3>
              <p className="text-xs text-brand-muted leading-relaxed">
                Pick an available consultation slot and obtain your unique appointment token.
              </p>
            </div>

            <div className="space-y-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep font-bold text-xs flex items-center justify-center shadow-xs">
                3
              </div>
              <h3 className="font-bold text-brand-text text-sm">
                Track Live Queue
              </h3>
              <p className="text-xs text-brand-muted leading-relaxed">
                Watch turns advance in real time through WebSocket updates from anywhere.
              </p>
            </div>

            <div className="space-y-2.5">
              <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep font-bold text-xs flex items-center justify-center shadow-xs">
                4
              </div>
              <h3 className="font-bold text-brand-text text-sm">
                Direct Consultation
              </h3>
              <p className="text-xs text-brand-muted leading-relaxed">
                Step directly into the designated consultation room when your token is called.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Trust, Privacy & Transparency Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="rounded-2xl bg-brand-ground border border-brand-border/90 p-6 sm:p-8 space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-brand-mint text-brand-deep flex items-center justify-center">
              <ClinicalIcon name="shield-check" size={18} ariaHidden="true" />
            </div>
            <h3 className="text-base font-bold text-brand-text">
              Privacy Safeguards &amp; Operational Transparency
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs text-brand-muted leading-relaxed">
            <div className="space-y-1">
              <h4 className="font-bold text-brand-text">Zero PII in Public Queues</h4>
              <p>
                Waiting room TV displays and live queue screens show only anonymous numeric tokens. Patient names, diagnoses, and medical histories are never broadcast.
              </p>
            </div>
            <div className="space-y-1">
              <h4 className="font-bold text-brand-text">Cookie-Based Security</h4>
              <p>
                Sessions are authenticated via secure HttpOnly cookies, protecting your account from cross-site script access and local token theft.
              </p>
            </div>
            <div className="space-y-1">
              <h4 className="font-bold text-brand-text">Simulated Demonstration</h4>
              <p>
                This demonstration environment operates on synthetic clinical and hospital records for system workflow evaluation.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
