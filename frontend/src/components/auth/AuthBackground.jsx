import React, { useState, useEffect, useRef } from 'react'

/**
 * AuthBackground
 *
 * A reusable cinematic healthcare video background component with:
 * - Full-viewport responsive coverage (`object-fit: cover`)
 * - Autoplay, loop, muted, playsInline video
 * - Deep teal healthcare overlay gradient for WCAG-compliant foreground text contrast
 * - Seamless high-resolution poster fallback (`/images/auth-poster.jpg`)
 * - Automatic detection of `prefers-reduced-motion` for accessibility
 * - Graceful degradation on video loading or codec errors
 * - Vertical scrolling on small mobile screens without clipping or overflow
 */
export default function AuthBackground({
  children,
  videoSrc = '/videos/auth-healthcare-bg.mp4',
  posterSrc = '/images/auth-poster.jpg',
  badgeText = 'MediSmart Healthcare Network',
  className = '',
}) {
  const [isVideoLoaded, setIsVideoLoaded] = useState(false)
  const [videoError, setVideoError] = useState(false)
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    }
    return false
  })
  const videoRef = useRef(null)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handleChange = (e) => {
      setPrefersReducedMotion(e.matches)
    }

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(handleChange)
      return () => mediaQuery.removeListener(handleChange)
    }
  }, [])

  return (
    <div
      className={`relative min-h-[calc(100vh-4rem)] w-full flex flex-col items-center justify-center py-10 sm:py-16 px-4 sm:px-6 overflow-x-hidden ${className}`}
    >
      {/* Background Media Container (Hidden from assistive technologies) */}
      <div
        className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none select-none z-0"
        aria-hidden="true"
      >
        {/* Fallback Poster Background Image */}
        <div
          className="absolute inset-0 w-full h-full bg-cover bg-center bg-no-repeat transform scale-105"
          style={{ backgroundImage: `url(${posterSrc})` }}
        />

        {/* Cinematic Video Element */}
        {!prefersReducedMotion && !videoError && (
          <video
            ref={videoRef}
            autoPlay
            muted
            loop
            playsInline
            poster={posterSrc}
            onLoadedData={() => setIsVideoLoaded(true)}
            onError={() => setVideoError(true)}
            tabIndex={-1}
            aria-hidden="true"
            className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-1000 ${
              isVideoLoaded ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <source src={videoSrc} type="video/mp4" onError={() => setVideoError(true)} />
            <source
              src={videoSrc.replace('.mp4', '.webm')}
              type="video/webm"
              onError={() => setVideoError(true)}
            />
          </video>
        )}

        {/* Deep Teal Healthcare Color Grading & Readability Overlay */}
        <div className="absolute inset-0 bg-gradient-to-tr from-[#062422]/90 via-[#0A3D3A]/82 to-[#147D77]/75 backdrop-blur-[1px]" />

        {/* Ambient Radial Lighting & Subtle Vignette */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-teal-400/12 via-transparent to-black/40" />
      </div>

      {/* Foreground Header & Brand Tagline */}
      <div className="relative z-10 w-full max-w-lg mb-6 text-center space-y-2">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-white text-[11px] font-medium tracking-wide shadow-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>{badgeText}</span>
        </div>
      </div>

      {/* Main Form Slot Container */}
      <div className="relative z-10 w-full flex justify-center">
        {children}
      </div>
    </div>
  )
}
