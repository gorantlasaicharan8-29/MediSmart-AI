import React, { useState, useEffect, useRef } from 'react'

const STORAGE_KEY = 'medismart_intro_played'

// Exact animation sequence (~1.65s total duration, within 1.5–2.0s requirement)
const STAGE_TAGLINE_START = 350   // Stage 2: Tagline begins smooth fade-in (~0.35s)
const STAGE_RING_ACTIVATE = 650   // Stage 3: Concentric teal/mint rings active (~0.65s)
const STAGE_REVEAL_START  = 1000  // Stage 4: Inside-out circular reveal begins from center (~1.0s)
const STAGE_COMPLETE      = 1650  // Stage 5: Transition complete & unmount (~1.65s)
const FAILSAFE_TIMEOUT    = 1850  // Guaranteed fallback unmount limit (< 2.0s)

/**
 * Checks whether the intro animation should be skipped:
 * 1. Server-side rendering fallback
 * 2. Testing override via URL query parameter (?intro=true)
 * 3. User prefers reduced motion (accessibility)
 * 4. Intro has already been played in the current browser tab session
 */
function shouldSkipIntro() {
  if (typeof window === 'undefined') return true
  try {
    // Development / testing override: ?intro=true forces intro playback
    if (window.location && window.location.search) {
      const params = new URLSearchParams(window.location.search)
      if (params.get('intro') === 'true') {
        return false
      }
    }

    if (
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return true
    }

    return window.sessionStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

/**
 * LogoIntro
 *
 * Premium, elegant healthcare logo-first intro animation for MediSmart AI:
 * - 100% solid pure white intro background (#FFFFFF) blocking homepage completely during Stages 1–3.
 * - Small, medium-compact centered MediSmart AI logo (Desktop 220px, Tablet 190px, Mobile 160px).
 * - Official tagline "SMART CARE. HEALTHIER LIVES." beneath the logo (12–16px spacing).
 * - Subtle concentric teal and mint circular rings (#0D9488, #14B8A6, #99F6E4).
 * - True inside-out circular reveal expanding from center point (scale 0 -> scale 220) to all corners.
 * - Automatic transition into the existing website in ~1.65s (under 2.0s).
 * - No Skip button, no manual click or keyboard bypass.
 * - Once-per-tab session enforcement via sessionStorage.
 * - Immediate bypass when prefers-reduced-motion is active.
 * - Strict timer cleanup & body overflow restoration on unmount.
 */
export default function LogoIntro() {
  const [stage, setStage] = useState(() => (shouldSkipIntro() ? 5 : 1))
  const timersRef = useRef([])

  useEffect(() => {
    // If intro should be skipped, do nothing
    if (shouldSkipIntro()) return

    // Lock body scrolling during intro overlay
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Stage 2: Tagline begins smooth fade-in
    const t1 = setTimeout(() => {
      setStage(2)
    }, STAGE_TAGLINE_START)

    // Stage 3: Concentric teal/mint rings activate
    const t2 = setTimeout(() => {
      setStage(3)
    }, STAGE_RING_ACTIVATE)

    // Stage 4: Inside-out circular reveal begins expanding from center point
    const t3 = setTimeout(() => {
      setStage(4)
    }, STAGE_REVEAL_START)

    // Stage 5: Unmount completely, mark session played & restore scrolling (~1.65s)
    const t4 = setTimeout(() => {
      setStage(5)
      try {
        window.sessionStorage.setItem(STORAGE_KEY, 'true')
      } catch {
        // Storage access safely handled
      }
      document.body.style.overflow = previousOverflow
    }, STAGE_COMPLETE)

    // Guaranteed failsafe timeout (< 2.0s)
    const tFailsafe = setTimeout(() => {
      setStage(5)
      try {
        window.sessionStorage.setItem(STORAGE_KEY, 'true')
      } catch {
        // Storage access safely handled
      }
      document.body.style.overflow = previousOverflow
    }, FAILSAFE_TIMEOUT)

    timersRef.current = [t1, t2, t3, t4, tFailsafe]

    return () => {
      timersRef.current.forEach(clearTimeout)
      document.body.style.overflow = previousOverflow
    }
  }, [])

  // When completed or skipped, unmount completely from DOM
  if (stage >= 5) return null

  const isRevealing = stage >= 4

  return (
    <div
      role="region"
      aria-label="MediSmart AI Introduction"
      className={`fixed inset-0 z-[9999] overflow-hidden select-none ${
        isRevealing ? 'pointer-events-none' : 'pointer-events-auto'
      }`}
    >
      {/* 1. Solid Pure White Backdrop (#FFFFFF)
          - 100% opaque, covers entire viewport during Stages 1–3
          - Completely blocks navbar, hero section, and homepage content
          - Fades out in 120ms when Stage 4 reveal begins */}
      <div
        className={`absolute inset-0 bg-white transition-opacity duration-120 ease-out pointer-events-none ${
          isRevealing ? 'opacity-0' : 'opacity-100'
        }`}
      />

      {/* 2. Inside-Out Circular Reveal Aperture
          - Positioned at the exact center (50%, 50%)
          - Starts at radius 0 (scale 0)
          - During Stage 4, smoothly expands outward from center to scale(220) (> 7000px diameter)
          - Glowing teal border (#14B8A6) forms the expanding leading edge
          - Box-shadow 250vmax keeps outside area 100% pure white as the circle expands */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div
          className="relative rounded-full will-change-transform"
          style={{
            width: '32px',
            height: '32px',
            border: '2px solid #14B8A6',
            boxShadow: '0 0 16px rgba(20, 184, 166, 0.45), 0 0 0 250vmax #ffffff',
            transform: isRevealing ? 'scale(220)' : 'scale(0)',
            transition: isRevealing
              ? 'transform 650ms cubic-bezier(0.25, 0.1, 0.25, 1)'
              : 'none',
          }}
        />
      </div>

      {/* 3. Center Branding & Subtle Concentric Teal/Mint Animation
          - Remains compact and perfectly centered throughout animation
          - Fades out cleanly when Stage 4 reveal starts, without enlarging */}
      <div
        className={`absolute inset-0 flex flex-col items-center justify-center pointer-events-none transition-opacity duration-150 ease-out ${
          isRevealing ? 'opacity-0' : 'opacity-100'
        }`}
      >
        {/* Concentric Healthcare Halo Rings: Subtle, Thin & Proportional */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {/* Outer Ring: Soft Mint Glow */}
          <div
            className="absolute rounded-full border border-[#99F6E4]/60 pointer-events-none"
            style={{
              width: 'clamp(270px, 47vw, 365px)',
              height: 'clamp(270px, 47vw, 365px)',
              boxShadow: '0 0 20px rgba(20, 184, 166, 0.08)',
              animation: 'introPulseGlow 3s ease-in-out infinite',
            }}
          />

          {/* Middle Ring: Rotating Thin Dashed Aqua Accent with Subtle Nodes */}
          <div
            className="absolute rounded-full border border-dashed border-[#14B8A6]/35 pointer-events-none"
            style={{
              width: 'clamp(235px, 41vw, 315px)',
              height: 'clamp(235px, 41vw, 315px)',
              animation: 'introSpinSlow 24s linear infinite',
            }}
          >
            {/* Top Node */}
            <span
              className="absolute -top-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-[#14B8A6]"
              style={{ boxShadow: '0 0 6px #14B8A6' }}
            />
            {/* Bottom Node */}
            <span
              className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-[#99F6E4]"
              style={{ boxShadow: '0 0 6px #99F6E4' }}
            />
          </div>

          {/* Inner Ring: Thin Subtle Teal Pulse */}
          <div
            className="absolute rounded-full border border-[#0D9488]/30 pointer-events-none"
            style={{
              width: 'clamp(200px, 35vw, 265px)',
              height: 'clamp(200px, 35vw, 265px)',
              animation: 'introPulseSubtle 2.5s ease-in-out infinite',
            }}
          />
        </div>

        {/* Small, Medium-Compact MediSmart AI Brand Composition */}
        <div className="relative z-10 flex flex-col items-center justify-center">
          {/* Stage 1: Official Logo (Emblem + MediSmart AI Wordmark) */}
          <div
            className="flex justify-center"
            style={{
              animation: 'introLogoFadeZoom 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards',
            }}
          >
            <img
              src="/images/medismart-intro-brand.png"
              alt="MediSmart AI Logo"
              className="w-[160px] sm:w-[190px] lg:w-[220px] max-w-[75vw] h-auto object-contain select-none pointer-events-none"
            />
          </div>

          {/* Stage 2: Official Tagline ("SMART CARE. HEALTHIER LIVES." + Heartbeat Pulse) */}
          <div
            className={`flex justify-center mt-3 sm:mt-3.5 transition-opacity duration-300 ease-out ${
              stage >= 2 ? 'opacity-100' : 'opacity-0 pointer-events-none'
            }`}
          >
            <img
              src="/images/medismart-intro-tagline.png"
              alt="Smart Care. Healthier Lives."
              className="w-[160px] sm:w-[190px] lg:w-[220px] max-w-[75vw] h-auto object-contain select-none pointer-events-none"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
