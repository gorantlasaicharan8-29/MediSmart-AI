import React, { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const navLinkClass = ({ isActive }) =>
    `text-sm font-medium transition-colors px-3 py-1.5 rounded-lg ${
      isActive
        ? 'text-teal-700 bg-teal-50/80 font-semibold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
    }`

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-teal-600 to-cyan-600 flex items-center justify-center text-white shadow-sm shadow-teal-700/20 group-hover:scale-105 transition-transform">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-slate-900 text-lg tracking-tight leading-none">
                Medi<span className="text-teal-600">Smart</span>
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-wide uppercase mt-0.5">
                Healthcare OS
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1.5">
            <NavLink to="/" className={navLinkClass}>
              Home
            </NavLink>
            <NavLink to="/hospitals" className={navLinkClass}>
              Find Hospitals
            </NavLink>
            <NavLink to="/doctors" className={navLinkClass}>
              Doctors
            </NavLink>
            <NavLink to="/queue" className={navLinkClass}>
              Live Queue
            </NavLink>
          </nav>

          {/* Auth Actions (Frontend Shell) */}
          <div className="hidden md:flex items-center gap-2.5">
            <Link
              to="/login"
              className="text-sm font-medium text-slate-700 hover:text-slate-900 px-3.5 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 px-4 py-2 rounded-lg shadow-sm hover:shadow transition-all"
            >
              Register
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none"
              aria-expanded={mobileMenuOpen}
            >
              <span className="sr-only">Open main menu</span>
              {mobileMenuOpen ? (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 bg-white px-4 pt-2 pb-4 space-y-1">
          <NavLink
            to="/"
            onClick={() => setMobileMenuOpen(false)}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-base font-medium ${
                isActive ? 'text-teal-700 bg-teal-50 font-semibold' : 'text-slate-700 hover:bg-slate-50'
              }`
            }
          >
            Home
          </NavLink>
          <NavLink
            to="/hospitals"
            onClick={() => setMobileMenuOpen(false)}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-base font-medium ${
                isActive ? 'text-teal-700 bg-teal-50 font-semibold' : 'text-slate-700 hover:bg-slate-50'
              }`
            }
          >
            Find Hospitals
          </NavLink>
          <NavLink
            to="/doctors"
            onClick={() => setMobileMenuOpen(false)}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-base font-medium ${
                isActive ? 'text-teal-700 bg-teal-50 font-semibold' : 'text-slate-700 hover:bg-slate-50'
              }`
            }
          >
            Doctors
          </NavLink>
          <NavLink
            to="/queue"
            onClick={() => setMobileMenuOpen(false)}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-base font-medium ${
                isActive ? 'text-teal-700 bg-teal-50 font-semibold' : 'text-slate-700 hover:bg-slate-50'
              }`
            }
          >
            Live Queue
          </NavLink>
          <div className="pt-3 border-t border-slate-100 flex gap-2">
            <Link
              to="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="flex-1 text-center py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              onClick={() => setMobileMenuOpen(false)}
              className="flex-1 text-center py-2 text-sm font-medium text-white bg-teal-600 rounded-lg"
            >
              Register
            </Link>
          </div>
        </div>
      )}
    </header>
  )
}
