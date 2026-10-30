import React, { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { Button, Badge, ClinicalIcon } from './ui'

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    setMobileMenuOpen(false)
    navigate('/login')
  }

  const isDoctorOrAdmin =
    user && ['doctor', 'hospital_admin', 'system_admin'].includes(user.role)

  const navLinkClass = ({ isActive }) =>
    `text-xs font-semibold px-3 py-2 rounded-xl transition-all duration-150 select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent ${
      isActive
        ? 'text-brand-deep bg-brand-mint/70 shadow-xs'
        : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
    }`

  const mobileNavLinkClass = ({ isActive }) =>
    `block px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
      isActive
        ? 'text-brand-deep bg-brand-mint/70 font-bold'
        : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
    }`

  const getRoleVariant = (role) => {
    switch (role) {
      case 'doctor':
        return 'info'
      case 'hospital_admin':
        return 'warning'
      case 'system_admin':
        return 'danger'
      default:
        return 'teal'
    }
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-brand-border bg-brand-surface/95 backdrop-blur-md transition-shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link
            to="/"
            className="flex items-center gap-2.5 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent rounded-xl p-1 transition-opacity hover:opacity-95"
            aria-label="MediSmart AI Home"
          >
            <img
              src="/images/medismart-icon.png"
              alt="MediSmart AI Logo"
              className="w-9 h-9 sm:w-10 sm:h-10 object-contain rounded-xl shadow-clinical-xs group-hover:scale-105 transition-transform shrink-0"
            />
            <div className="flex flex-col">
              <span className="font-bold text-brand-text text-lg tracking-tight leading-none flex items-center gap-1.5">
                Medi<span className="text-brand-accent">Smart</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-brand-mint/80 text-brand-deep border border-teal-200/80 uppercase tracking-wide leading-none">
                  AI
                </span>
              </span>
              <span className="text-[10px] text-brand-muted font-medium tracking-wider uppercase mt-0.5">
                Smart Care. Healthier Lives.
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1.5" aria-label="Main Navigation">
            <NavLink to="/" end className={navLinkClass}>
              Home
            </NavLink>
            <NavLink to="/hospitals" className={navLinkClass}>
              Hospitals
            </NavLink>
            <NavLink to="/doctors" className={navLinkClass}>
              Doctors
            </NavLink>
            {isAuthenticated && (
              <NavLink to="/appointments" className={navLinkClass}>
                Appointments
              </NavLink>
            )}
            <NavLink to="/queue" className={navLinkClass}>
              Live Queue
            </NavLink>
            {isDoctorOrAdmin && (
              <NavLink to="/doctor" className={navLinkClass}>
                Doctor Workspace
              </NavLink>
            )}
          </nav>

          {/* Desktop Auth Controls */}
          <div className="hidden md:flex items-center gap-3">
            {isAuthenticated ? (
              <div className="flex items-center gap-3 pl-2 border-l border-brand-border/70">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-brand-mint text-brand-deep border border-teal-200 flex items-center justify-center text-xs font-bold shadow-clinical-xs select-none">
                    {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                  </div>
                  <div className="flex flex-col text-left">
                    <span className="text-xs font-bold text-brand-text leading-tight truncate max-w-[140px]">
                      {user?.full_name}
                    </span>
                    <Badge
                      variant={getRoleVariant(user?.role)}
                      size="sm"
                      className="mt-0.5 w-fit uppercase text-[9px] tracking-wider py-0"
                    >
                      {user?.role?.replace('_', ' ')}
                    </Badge>
                  </div>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                  className="text-xs text-brand-muted hover:text-clinical-danger hover:border-red-200 hover:bg-red-50/60"
                >
                  Sign Out
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button
                  as={Link}
                  to="/login"
                  variant="ghost"
                  size="sm"
                  className="text-xs font-semibold text-brand-text"
                >
                  Sign In
                </Button>
                <Button
                  as={Link}
                  to="/register"
                  variant="primary"
                  size="sm"
                  className="text-xs font-semibold"
                >
                  Register
                </Button>
              </div>
            )}
          </div>

          {/* Mobile Menu Hamburger */}
          <div className="flex md:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-xl text-brand-muted hover:text-brand-text hover:bg-brand-ground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer"
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle navigation menu"
            >
              <ClinicalIcon
                name={mobileMenuOpen ? 'x' : 'filter'}
                size={22}
                ariaHidden="true"
              />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-brand-border bg-brand-surface px-4 pt-2 pb-5 space-y-1 shadow-clinical-md">
          <NavLink
            to="/"
            end
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Home
          </NavLink>
          <NavLink
            to="/hospitals"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Find Hospitals
          </NavLink>
          <NavLink
            to="/doctors"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Find Doctors
          </NavLink>
          {isAuthenticated && (
            <NavLink
              to="/appointments"
              onClick={() => setMobileMenuOpen(false)}
              className={mobileNavLinkClass}
            >
              My Appointments
            </NavLink>
          )}
          <NavLink
            to="/queue"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Live Queue Tracking
          </NavLink>
          {isDoctorOrAdmin && (
            <NavLink
              to="/doctor"
              onClick={() => setMobileMenuOpen(false)}
              className={mobileNavLinkClass}
            >
              Doctor Workspace
            </NavLink>
          )}

          {/* Mobile Auth Drawer Segment */}
          <div className="pt-3 mt-2 border-t border-brand-border/80">
            {isAuthenticated ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3 px-1 py-1">
                  <div className="w-9 h-9 rounded-full bg-brand-mint text-brand-deep border border-teal-200 flex items-center justify-center text-sm font-bold">
                    {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                  </div>
                  <div>
                    <div className="text-sm font-bold text-brand-text">
                      {user?.full_name}
                    </div>
                    <Badge
                      variant={getRoleVariant(user?.role)}
                      size="sm"
                      className="mt-0.5 uppercase text-[9px]"
                    >
                      {user?.role?.replace('_', ' ')}
                    </Badge>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleLogout}
                  className="w-full text-clinical-danger border-red-200 hover:bg-red-50"
                >
                  Sign Out
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 pt-1">
                <Button
                  as={Link}
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  variant="outline"
                  size="md"
                  className="w-full text-xs font-semibold"
                >
                  Sign In
                </Button>
                <Button
                  as={Link}
                  to="/register"
                  onClick={() => setMobileMenuOpen(false)}
                  variant="primary"
                  size="md"
                  className="w-full text-xs font-semibold"
                >
                  Register
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  )
}
