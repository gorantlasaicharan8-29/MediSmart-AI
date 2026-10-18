import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { checkBackendHealth, checkDatabaseHealth } from '../services/api'

export default function Home() {
  const [healthStatus, setHealthStatus] = useState({
    backend: 'checking...',
    database: 'checking...',
    checked: false,
  })

  useEffect(() => {
    async function loadHealth() {
      const [backend, db] = await Promise.all([
        checkBackendHealth(),
        checkDatabaseHealth(),
      ])
      setHealthStatus({
        backend: backend.status === 'ok' ? 'Connected' : 'Offline',
        database: db.status === 'ok' && db.database === 'connected' ? 'Connected' : 'Offline',
        checked: true,
      })
    }
    loadHealth()
  }, [])

  return (
    <div className="space-y-16 py-8 md:py-12">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 space-y-6">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-teal-50 border border-teal-200/80 text-teal-800 text-xs font-semibold tracking-wide">
                <span className="w-2 h-2 rounded-full bg-teal-600"></span>
                Modern Healthcare Operations Platform
              </div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 border border-slate-200 text-slate-700 text-xs font-medium">
                <span
                  className={`w-2 h-2 rounded-full ${
                    healthStatus.database === 'Connected' ? 'bg-emerald-500' : 'bg-amber-500'
                  }`}
                ></span>
                <span>
                  Backend: {healthStatus.backend} • DB: {healthStatus.database}
                </span>
              </div>
            </div>

            <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-[1.15]">
              Find Nearby Hospitals, Book Verified Doctors, &amp;{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-700 to-cyan-700">
                Skip the Waiting Room
              </span>
            </h1>

            <p className="text-lg text-slate-600 leading-relaxed max-w-2xl">
              MediSmart combines real-time geographic hospital discovery with digital queue tokens, WebSocket live waiting updates, and AI wait-time estimation.
            </p>

            {/* Quick Action Search Bar Mockup */}
            <div className="p-2 sm:p-2.5 rounded-2xl bg-white border border-slate-200 shadow-sm max-w-xl flex flex-col sm:flex-row gap-2">
              <div className="flex-1 flex items-center gap-2.5 px-3 py-2 text-slate-400">
                <svg className="w-5 h-5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 1114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search hospital, specialty, or area..."
                  className="w-full text-sm text-slate-800 placeholder-slate-400 bg-transparent focus:outline-none"
                  readOnly
                />
              </div>
              <Link
                to="/hospitals"
                className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold transition-all shadow-sm"
              >
                Explore Map
              </Link>
            </div>

            {/* Micro proof badges */}
            <div className="pt-2 flex flex-wrap items-center gap-6 text-xs text-slate-500">
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-teal-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Interactive OpenStreetMap</span>
              </div>
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-teal-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>Live Digital Queue Tokens</span>
              </div>
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-teal-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                <span>ML Wait Prediction</span>
              </div>
            </div>
          </div>

          {/* Hero Visual Card: Live Queue Preview Widget */}
          <div className="lg:col-span-5">
            <div className="relative rounded-2xl bg-white border border-slate-200/90 shadow-lg shadow-slate-200/50 p-6 space-y-5">
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-teal-100 text-teal-700 flex items-center justify-center font-bold text-xs">
                    Q
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900 leading-tight">Live Consultation Queue</h2>
                    <p className="text-xs text-slate-500">City General Hospital • Cardiology</p>
                  </div>
                </div>
                <span className="px-2.5 py-1 text-[11px] font-semibold bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200">
                  Live Active
                </span>
              </div>

              {/* Token Display */}
              <div className="rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 text-white p-5 space-y-3">
                <div className="flex justify-between items-start">
                  <span className="text-xs uppercase tracking-wider text-slate-400 font-medium">Current Turn</span>
                  <span className="text-xs font-semibold text-teal-400">Token #42 in room</span>
                </div>
                <div className="flex items-baseline gap-4">
                  <div className="text-3xl font-extrabold tracking-tight">Token #45</div>
                  <div className="text-xs text-slate-300">Your simulated position</div>
                </div>
                <div className="pt-2 border-t border-slate-700/60 flex items-center justify-between text-xs text-slate-300">
                  <span>Patients Ahead: <strong className="text-white">2</strong></span>
                  <span>Est. Wait: <strong className="text-teal-300">~14 mins</strong></span>
                </div>
              </div>

              {/* Status Flow */}
              <div className="space-y-2 pt-1 text-xs">
                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-600">Dr. Sarah Mitchell, MD</span>
                  <span className="font-medium text-slate-900">Room 304</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-slate-600">PostgreSQL medismart_db</span>
                  <span className={`font-medium ${healthStatus.database === 'Connected' ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {healthStatus.database === 'Connected' ? 'Connected (5 Tables Active)' : 'Connecting...'}
                  </span>
                </div>
              </div>

              <div className="pt-2">
                <Link
                  to="/register"
                  className="block w-full text-center py-2.5 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition-colors"
                >
                  Create Patient Account to Track
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Pillars */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-12 space-y-2">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900">
            Engineered for Patients, Doctors, &amp; Hospitals
          </h2>
          <p className="text-sm text-slate-500">
            A cohesive architecture connecting discovery, appointment scheduling, and queue coordination.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow space-y-3">
            <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center font-bold">
              🗺️
            </div>
            <h3 className="font-bold text-slate-900 text-base">Interactive Maps</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Find facilities using OpenStreetMap and Leaflet markers with real geographic coordinates, specialty filters, and distance sorting.
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow space-y-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-50 text-cyan-600 flex items-center justify-center font-bold">
              🩺
            </div>
            <h3 className="font-bold text-slate-900 text-base">Doctor Discovery</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Explore specialist qualifications, verified consultation fees, and schedule appointments with conflict-free slot validation.
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              ⏱️
            </div>
            <h3 className="font-bold text-slate-900 text-base">Real-Time Queues</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Digital tokens with WebSocket live broadcasts notify patients as their turns advance without requiring crowded waiting halls.
            </p>
          </div>

          {/* Card 4 */}
          <div className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-xs hover:shadow-md transition-shadow space-y-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              🧠
            </div>
            <h3 className="font-bold text-slate-900 text-base">Predictive ML</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Machine learning models forecast dynamic wait times and predict potential no-shows to assist clinics with schedule optimization.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
