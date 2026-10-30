import React from 'react'
import { Link } from 'react-router-dom'
import { Badge } from './ui'

const CURRENT_YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="bg-brand-surface border-t border-brand-border mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand Info */}
          <div className="md:col-span-2 space-y-3.5">
            <Link
              to="/"
              className="inline-flex items-center gap-2.5 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent rounded-xl"
              aria-label="MediSmart AI Home"
            >
              <img
                src="/images/medismart-icon.png"
                alt="MediSmart AI Logo"
                className="w-8 h-8 object-contain rounded-xl shadow-clinical-xs group-hover:scale-105 transition-transform shrink-0"
              />
              <span className="font-bold text-brand-text text-base tracking-tight flex items-center gap-1.5">
                Medi<span className="text-brand-accent">Smart</span>
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-brand-mint/80 text-brand-deep border border-teal-200/80 uppercase tracking-wide leading-none">
                  AI
                </span>
              </span>
            </Link>
            <p className="text-xs text-brand-muted max-w-md leading-relaxed">
              Open healthcare operations platform providing interactive hospital discovery, specialist appointment scheduling, and real-time digital queue management.
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge variant="teal" size="sm" dot>
                Smart Care. Healthier Lives.
              </Badge>
              <Badge variant="neutral" size="sm">
                FastAPI Async &amp; PostgreSQL
              </Badge>
              <Badge variant="mint" size="sm">
                Tailwind CSS v4 &amp; React 19
              </Badge>
            </div>
          </div>

          {/* Platform Navigation */}
          <div>
            <h4 className="text-xs font-bold text-brand-text uppercase tracking-wider mb-3">
              Platform Discovery
            </h4>
            <ul className="space-y-2 text-xs text-brand-muted">
              <li>
                <Link
                  to="/hospitals"
                  className="hover:text-brand-deep hover:underline transition-colors"
                >
                  Interactive Hospital Map
                </Link>
              </li>
              <li>
                <Link
                  to="/doctors"
                  className="hover:text-brand-deep hover:underline transition-colors"
                >
                  Specialist Directory
                </Link>
              </li>
              <li>
                <Link
                  to="/queue"
                  className="hover:text-brand-deep hover:underline transition-colors"
                >
                  Public Live Queue
                </Link>
              </li>
              <li>
                <Link
                  to="/appointments"
                  className="hover:text-brand-deep hover:underline transition-colors"
                >
                  Patient Appointments
                </Link>
              </li>
            </ul>
          </div>

          {/* System Transparency & Disclaimer */}
          <div>
            <h4 className="text-xs font-bold text-brand-text uppercase tracking-wider mb-3">
              Demonstration &amp; Privacy
            </h4>
            <p className="text-xs text-brand-muted leading-relaxed">
              MediSmart operates on demonstration simulation records. Public queue displays do not expose protected health information or personal identities.
            </p>
            <div className="mt-4 pt-3 border-t border-brand-border/60 text-[11px] text-brand-muted/70">
              MediSmart AI &copy; {CURRENT_YEAR}. All rights reserved.
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
