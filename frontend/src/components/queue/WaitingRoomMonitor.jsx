import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDoctorPublicBoard, getDoctors } from '../../services/api'
import { useQueueSocket } from '../../hooks/useQueueSocket'
import { playChime } from '../../utils/sound'
import { ClinicalIcon } from '../ui'

export default function WaitingRoomMonitor({ initialDoctorId = null, standalone = false }) {
  const { doctorId: routeDoctorId } = useParams()
  const navigate = useNavigate()

  // Selected doctor ID from prop, URL param, or local selection
  const [selectedDoctorId, setSelectedDoctorId] = useState(
    initialDoctorId || routeDoctorId || ''
  )
  const [doctorsList, setDoctorsList] = useState([])
  const [isLoadingDoctors, setIsLoadingDoctors] = useState(false)

  // Public board state
  const [boardData, setBoardData] = useState(null)
  const [boardLoading, setBoardLoading] = useState(true)
  const [boardError, setBoardError] = useState(null)

  // Audio mute toggle (audio context requires user interaction before playing)
  const [isAudioMuted, setIsAudioMuted] = useState(false)
  const [justCalledFlash, setJustCalledFlash] = useState(false)
  const prevServingTokenRef = useRef(null)

  // Live clock display for waiting room display
  const [currentTime, setCurrentTime] = useState(() => new Date())
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Update clock every second
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Fullscreen state listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  // Toggle Fullscreen helper
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen().catch(() => {})
    }
  }

  // Fetch list of doctors for the selector
  useEffect(() => {
    let isMounted = true
    const loadDoctors = async () => {
      setIsLoadingDoctors(true)
      try {
        const res = await getDoctors({ page_size: 50 })
        if (isMounted) {
          const docs = res.items || res || []
          setDoctorsList(docs)
          // If no doctor selected yet, default to first doctor
          if (!selectedDoctorId && docs.length > 0) {
            setSelectedDoctorId(docs[0].id)
          }
        }
      } catch {
        // Fallback or quiet fail for doctors list
      } finally {
        if (isMounted) setIsLoadingDoctors(false)
      }
    }
    loadDoctors()
    return () => {
      isMounted = false
    }
  }, [selectedDoctorId])

  // Fetch public board for selected doctor
  const fetchBoard = useCallback(async () => {
    if (!selectedDoctorId) {
      setBoardData(null)
      setBoardLoading(false)
      return null
    }

    try {
      const data = await getDoctorPublicBoard(selectedDoctorId)
      setBoardData(data)
      setBoardError(null)

      // Check if current consultation token changed
      const currentServing = data?.current_consultation?.token_display || null
      if (
        currentServing &&
        prevServingTokenRef.current &&
        prevServingTokenRef.current !== currentServing
      ) {
        // Trigger pulse highlight and chime
        setJustCalledFlash(true)
        setTimeout(() => setJustCalledFlash(false), 3500)
        if (!isAudioMuted) {
          playChime('call')
        }
      }
      prevServingTokenRef.current = currentServing

      return data
    } catch (err) {
      setBoardError(err.message || 'Unable to load waiting room board')
      throw err
    } finally {
      setBoardLoading(false)
    }
  }, [selectedDoctorId, isAudioMuted])

  // Real-time WebSocket hook with 10s fallback polling
  const { isLive, connectionMode, lastRefreshed, refresh } = useQueueSocket({
    doctorId: selectedDoctorId || null,
    fetcher: fetchBoard,
    enabled: Boolean(selectedDoctorId),
    pollingInterval: 10000,
    onEvent: (event) => {
      if (event.action === 'PATIENT_CALLED') {
        setJustCalledFlash(true)
        setTimeout(() => setJustCalledFlash(false), 3500)
        if (!isAudioMuted) {
          playChime('call')
        }
      }
    },
  })

  // Handle doctor selection change
  const handleDoctorChange = (e) => {
    const newId = e.target.value
    setSelectedDoctorId(newId)
    setBoardLoading(true)
    if (standalone) {
      navigate(`/queue/monitor/${newId}`, { replace: true })
    }
  }

  const currentServing = boardData?.current_consultation
  const waitingList = boardData?.waiting_list || []

  return (
    <div
      className={`min-h-[85vh] flex flex-col justify-between transition-colors ${
        standalone
          ? 'bg-slate-950 text-slate-100 p-4 sm:p-8 min-h-screen'
          : 'bg-slate-900 text-slate-100 rounded-3xl p-6 sm:p-8 shadow-clinical-lg border border-slate-800'
      }`}
    >
      {/* Top Bar: Clinic Name, Clock, Controls */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
            <ClinicalIcon name="hospital" size={24} ariaHidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-teal-400">
                Waiting Room Display
              </span>
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                  isLive
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : connectionMode === 'polling'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isLive
                      ? 'bg-emerald-400 animate-pulse'
                      : connectionMode === 'polling'
                      ? 'bg-amber-400'
                      : 'bg-slate-500'
                  }`}
                />
                {isLive ? 'LIVE STREAM' : connectionMode === 'polling' ? 'POLLING (10s)' : 'CONNECTING'}
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight mt-0.5">
              {boardData?.hospital_name || 'MediSmart Healthcare Clinic'}
            </h1>
          </div>
        </div>

        {/* Doctor Selector & Controls */}
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-between md:justify-end">
          {/* Doctor Selection Dropdown */}
          <div className="relative">
            <select
              aria-label="Select Doctor Queue"
              value={selectedDoctorId}
              onChange={handleDoctorChange}
              disabled={isLoadingDoctors}
              className="bg-slate-800/90 hover:bg-slate-800 text-slate-200 text-xs sm:text-sm font-semibold rounded-xl border border-slate-700 px-3.5 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-teal-500 transition-all appearance-none cursor-pointer"
            >
              {doctorsList.length === 0 ? (
                <option value="">Loading Doctors...</option>
              ) : (
                doctorsList.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    Dr. {doc.full_name} ({doc.specialty})
                  </option>
                ))
              )}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5 text-slate-400 text-xs">
              <ClinicalIcon name="chevron-down" size={12} ariaHidden="true" />
            </div>
          </div>

          {/* Clock */}
          <div className="font-mono text-base sm:text-lg font-bold text-slate-200 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700/60 tracking-wider">
            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>

          {/* Audio Chime Mute/Unmute */}
          <button
            type="button"
            onClick={() => setIsAudioMuted(!isAudioMuted)}
            className={`p-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
              isAudioMuted
                ? 'bg-slate-800 text-slate-400 border-slate-700'
                : 'bg-teal-500/15 text-teal-300 border-teal-500/30'
            }`}
            title={isAudioMuted ? 'Unmute Audio Chime' : 'Mute Audio Chime'}
            aria-label={isAudioMuted ? 'Unmute audio chime' : 'Mute audio chime'}
          >
            <ClinicalIcon name={isAudioMuted ? 'alert-triangle' : 'sparkles'} size={16} ariaHidden="true" />
          </button>

          {/* Fullscreen Button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all text-xs font-semibold cursor-pointer"
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen TV Mode'}
            aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            <ClinicalIcon name="chevron-right" size={16} ariaHidden="true" />
          </button>

          {/* Refresh Manual Trigger */}
          <button
            type="button"
            onClick={() => refresh()}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-all text-xs font-semibold cursor-pointer"
            title="Refresh Display"
            aria-label="Refresh waiting room display"
          >
            <ClinicalIcon name="refresh" size={16} ariaHidden="true" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {boardLoading && !boardData ? (
        <div className="py-24 text-center space-y-4">
          <div className="w-10 h-10 border-3 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-semibold text-slate-400">Loading waiting room display...</p>
        </div>
      ) : boardError && !boardData ? (
        <div className="py-20 text-center space-y-4 max-w-md mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto border border-rose-500/20">
            <ClinicalIcon name="alert-circle" size={28} ariaHidden="true" />
          </div>
          <h3 className="text-lg font-bold text-white">Display Unavailable</h3>
          <p className="text-xs text-slate-400">{boardError}</p>
          <button
            type="button"
            onClick={() => refresh()}
            className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition-all cursor-pointer"
          >
            Retry Connection
          </button>
        </div>
      ) : (
        <div className="py-6 space-y-6 flex-1">
          {/* Doctor Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-6 py-4 rounded-2xl bg-slate-800/50 border border-slate-800">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-teal-400">
                Consulting Room
              </span>
              <h2 className="text-lg sm:text-xl font-black text-white">
                {boardData?.doctor_name ? `Dr. ${boardData.doctor_name}` : 'Doctor Console'}
              </h2>
              <p className="text-xs text-slate-400">{boardData?.specialty || 'General Medicine'}</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-semibold text-slate-400">
              <div>
                Date: <span className="text-slate-200">{boardData?.queue_date}</span>
              </div>
              <div>
                Patients Waiting:{' '}
                <span className="text-teal-400 font-bold font-mono text-sm">
                  {boardData?.total_waiting || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Grid Layout: Left Hero (Now Serving) | Right (Next In Line) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* HERO CARD: CURRENTLY IN CONSULTATION (7 cols) */}
            <div
              className={`lg:col-span-7 rounded-3xl p-8 sm:p-10 border transition-all duration-500 flex flex-col justify-between min-h-[380px] shadow-2xl relative overflow-hidden ${
                justCalledFlash
                  ? 'bg-gradient-to-br from-teal-900 via-emerald-950 to-slate-900 border-teal-400 ring-4 ring-teal-400/30 scale-[1.01]'
                  : 'bg-gradient-to-br from-slate-800/90 via-slate-800/60 to-slate-900/90 border-slate-700/80'
              }`}
            >
              {/* Top status indicator in hero */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-3.5 w-3.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-emerald-500" />
                  </span>
                  <span className="text-xs sm:text-sm font-black tracking-widest uppercase text-emerald-400">
                    Now Serving in Room
                  </span>
                </div>
                {justCalledFlash && (
                  <span className="px-3 py-1 rounded-full bg-teal-400/20 text-teal-300 text-xs font-black uppercase tracking-wider animate-pulse border border-teal-400/30">
                    Called Just Now
                  </span>
                )}
              </div>

              {/* Massive Token Number Display */}
              <div className="py-8 text-center my-auto">
                {currentServing ? (
                  <div className="space-y-3">
                    <div className="font-mono text-7xl sm:text-8xl md:text-9xl font-black text-white tracking-tighter drop-shadow-md select-none">
                      {currentServing.token_display}
                    </div>
                    <div className="text-sm sm:text-base font-bold text-emerald-400 uppercase tracking-widest">
                      Token #{currentServing.token_number} • Consultation in Progress
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3 text-slate-500">
                    <div className="text-5xl sm:text-6xl font-black tracking-tight select-none">
                      ---
                    </div>
                    <p className="text-sm font-semibold tracking-wide text-slate-400 uppercase">
                      Consultation Room Available • Awaiting Next Call
                    </p>
                  </div>
                )}
              </div>

              {/* Bottom Hero Footer */}
              <div className="pt-4 border-t border-slate-700/60 flex items-center justify-between text-xs text-slate-400">
                <span>Please proceed promptly to the consultation room when called.</span>
                <span className="font-mono text-slate-500">MediSmart Live Audio</span>
              </div>
            </div>

            {/* UPCOMING WAITING QUEUE (5 cols) */}
            <div className="lg:col-span-5 rounded-3xl bg-slate-800/40 border border-slate-800 p-6 sm:p-7 space-y-4 shadow-lg">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black uppercase tracking-widest text-slate-300">
                    Next in Line
                  </span>
                  <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 text-xs font-mono font-bold">
                    {waitingList.length}
                  </span>
                </div>
                <span className="text-[11px] text-slate-500 font-medium">Estimated Wait</span>
              </div>

              {waitingList.length === 0 ? (
                <div className="py-16 text-center space-y-2">
                  <div className="w-10 h-10 rounded-full bg-slate-800 text-slate-500 flex items-center justify-center mx-auto">
                    <ClinicalIcon name="check" size={20} ariaHidden="true" />
                  </div>
                  <h4 className="text-sm font-bold text-slate-300">Queue is Clear</h4>
                  <p className="text-xs text-slate-500">
                    No other patients are currently waiting for this doctor.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
                  {waitingList.map((item) => {
                    const isNext = item.position === 1
                    return (
                      <div
                        key={`${item.token_number}-${item.position}`}
                        className={`flex items-center justify-between p-3.5 rounded-2xl border transition-all ${
                          isNext
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-200 ring-1 ring-amber-500/20'
                            : 'bg-slate-800/60 border-slate-700/50 hover:bg-slate-800 text-slate-200'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          {/* Position Badge */}
                          <div
                            className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${
                              isNext
                                ? 'bg-amber-400 text-slate-950 font-black'
                                : 'bg-slate-700 text-slate-300'
                            }`}
                          >
                            #{item.position}
                          </div>

                          {/* Token Display */}
                          <div>
                            <div className="font-mono text-xl sm:text-2xl font-black tracking-tight">
                              {item.token_display}
                            </div>
                            {isNext && (
                              <span className="text-[10px] font-black uppercase tracking-wider text-amber-400 block mt-0.5">
                                Next Patient
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Estimated Wait */}
                        <div className="text-right">
                          <div className="font-mono font-bold text-sm text-slate-200">
                            ~{item.estimated_wait_minutes ?? 15} min
                          </div>
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider block">
                            Wait
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Screen Footer with Privacy & Live Sync Info */}
      <div className="pt-6 mt-6 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-500">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-500" />
          <span>
            Zero-PII Public Display • Tokens only. Patient identities and clinical records remain strictly confidential.
          </span>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          {lastRefreshed && (
            <span>
              Synced {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <span>MediSmart Kiosk Engine v5.3</span>
        </div>
      </div>
    </div>
  )
}
