import React from 'react'
import { Link } from 'react-router-dom'

const CURRENT_YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="bg-white border-t border-slate-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand Info */}
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-teal-600 flex items-center justify-center text-white font-bold text-xs">
                +
              </div>
              <span className="font-bold text-slate-900 text-base">MediSmart</span>
            </div>
            <p className="text-sm text-slate-500 max-w-sm leading-relaxed">
              Smart hospital discovery, doctor appointments, and real-time digital queue management powered by wait-time intelligence.
            </p>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/60 text-emerald-800 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              FastAPI & PostgreSQL 18.6 Stack
            </div>
          </div>

          {/* Platform Links */}
          <div>
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">
              Platform
            </h4>
            <ul className="space-y-2 text-sm text-slate-600">
              <li>
                <Link to="/hospitals" className="hover:text-teal-600 transition-colors">
                  Interactive Hospital Map
                </Link>
              </li>
              <li>
                <Link to="/doctors" className="hover:text-teal-600 transition-colors">
                  Find Specialists
                </Link>
              </li>
              <li>
                <Link to="/queue" className="hover:text-teal-600 transition-colors">
                  Live Queue Tracking
                </Link>
              </li>
              <li>
                <a
                  href="http://localhost:8000/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-teal-600 transition-colors inline-flex items-center gap-1"
                >
                  Backend API Docs
                  <span className="text-[10px] text-slate-400">↗</span>
                </a>
              </li>
            </ul>
          </div>

          {/* Notice & Disclaimer */}
          <div>
            <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">
              Demonstration Notice
            </h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              This system uses <strong className="text-slate-700">[SYNTHETIC DATA]</strong> for clinical and hospital simulations. No real patient data is stored.
            </p>
            <div className="mt-3 text-xs text-slate-400">
              MediSmart Platform &copy; {CURRENT_YEAR}
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
