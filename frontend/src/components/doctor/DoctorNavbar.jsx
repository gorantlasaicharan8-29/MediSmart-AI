import React, { useState, useEffect } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { getNotifications } from '../../services/api'
import { Button, Badge, ClinicalIcon } from '../ui'

export default function DoctorNavbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Poll or fetch unread count for badge
  useEffect(() => {
    let ignore = false
    const fetchUnread = async () => {
      try {
        const data = await getNotifications({ limit: 1 })
        if (!ignore && data?.unread_count !== undefined) {
          setUnreadCount(data.unread_count)
        }
      } catch {
        // Silently ignore if notifications table/endpoint unavailable
      }
    }
    fetchUnread()
    const timer = setInterval(fetchUnread, 30000)
    return () => {
      ignore = true
      clearInterval(timer)
    }
  }, [])

  const handleLogout = async () => {
    await logout()
    setMobileMenuOpen(false)
    navigate('/login')
  }

  const navLinkClass = ({ isActive }) =>
    `text-xs font-semibold px-3 py-2 rounded-xl transition-all duration-150 select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent ${
      isActive
        ? 'text-brand-deep bg-brand-mint/80 font-bold shadow-xs'
        : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
    }`

  const mobileNavLinkClass = ({ isActive }) =>
    `block px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
      isActive
        ? 'text-brand-deep bg-brand-mint/80 font-bold'
        : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
    }`

  // Format initials
  const displayName = user?.full_name?.startsWith('Dr.')
    ? user.full_name
    : `Dr. ${user?.full_name || 'Doctor'}`
  const initials = (user?.full_name || 'DR')
    .replace('Dr. ', '')
    .split(' ')
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="sticky top-0 z-40 w-full border-b border-brand-border bg-brand-surface/95 backdrop-blur-md transition-shadow shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Doctor Workspace Badge */}
          <Link
            to="/doctor"
            className="flex items-center gap-2.5 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent rounded-xl p-1 transition-opacity hover:opacity-95"
            aria-label="MediSmart AI Doctor Workspace"
          >
            <img
              src="/images/medismart-icon.png"
              alt="MediSmart AI Logo"
              className="w-9 h-9 sm:w-10 sm:h-10 object-contain rounded-xl shadow-clinical-xs group-hover:scale-105 transition-transform shrink-0"
            />
            <div className="flex flex-col">
              <span className="font-bold text-brand-text text-lg tracking-tight leading-none flex items-center gap-1.5">
                Medi<span className="text-brand-accent">Smart</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-teal-800 text-white uppercase tracking-wide leading-none">
                  Doctor
                </span>
              </span>
              <span className="text-[10px] text-brand-muted font-medium tracking-wider uppercase mt-0.5">
                Clinical Workspace
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Menu (Doctor-Specific) */}
          <nav className="hidden lg:flex items-center gap-1" aria-label="Doctor Navigation">
            <NavLink to="/doctor" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/doctor/appointments" className={navLinkClass}>
              My Appointments
            </NavLink>
            <NavLink to="/doctor/queue" className={navLinkClass}>
              Patient Queue
            </NavLink>
            <NavLink to="/doctor/schedule" className={navLinkClass}>
              My Schedule
            </NavLink>
            <NavLink to="/doctor/notifications" className={navLinkClass}>
              <span className="flex items-center gap-1.5">
                <span>Notifications</span>
                {unreadCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-clinical-danger text-white text-[10px] font-bold leading-none animate-pulse">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </span>
            </NavLink>
            <NavLink to="/doctor/profile" className={navLinkClass}>
              My Profile
            </NavLink>
          </nav>

          {/* Right-Side Controls */}
          <div className="hidden md:flex items-center gap-3">
            {/* Notification Bell Icon */}
            <NavLink
              to="/doctor/notifications"
              className="relative p-2 rounded-xl text-brand-muted hover:text-brand-text hover:bg-brand-ground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent"
              aria-label="View notifications"
            >
              <ClinicalIcon name="bell" size={20} ariaHidden="true" />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-clinical-danger ring-2 ring-white" />
              )}
            </NavLink>

            {/* Doctor Profile Summary */}
            <div className="flex items-center gap-2.5 pl-2 border-l border-brand-border/70">
              <NavLink
                to="/doctor/profile"
                className="flex items-center gap-2.5 group p-1 rounded-xl hover:bg-brand-ground transition-colors"
                title="View Doctor Profile"
              >
                <div className="w-8 h-8 rounded-full bg-brand-primary text-white font-bold flex items-center justify-center text-xs shadow-clinical-xs select-none group-hover:scale-105 transition-transform">
                  {initials}
                </div>
                <div className="flex flex-col text-left">
                  <span className="text-xs font-bold text-brand-text leading-tight truncate max-w-[140px]">
                    {displayName}
                  </span>
                  <Badge
                    variant="info"
                    size="sm"
                    className="mt-0.5 w-fit uppercase text-[9px] tracking-wider py-0"
                  >
                    Doctor
                  </Badge>
                </div>
              </NavLink>

              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="text-xs text-brand-muted hover:text-clinical-danger hover:border-red-200 hover:bg-red-50/60 ml-1"
              >
                Sign Out
              </Button>
            </div>
          </div>

          {/* Mobile Hamburger Button */}
          <div className="flex lg:hidden items-center gap-2">
            <NavLink
              to="/doctor/notifications"
              className="relative p-2 rounded-xl text-brand-muted hover:text-brand-text hover:bg-brand-ground transition-colors"
              aria-label="View notifications"
            >
              <ClinicalIcon name="bell" size={20} ariaHidden="true" />
              {unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-clinical-danger ring-2 ring-white" />
              )}
            </NavLink>

            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-xl text-brand-muted hover:text-brand-text hover:bg-brand-ground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer"
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle doctor navigation menu"
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
        <div className="lg:hidden border-b border-brand-border bg-brand-surface px-4 pt-2 pb-5 space-y-1 shadow-clinical-md animate-fade-in">
          {/* Doctor Info in Mobile Drawer */}
          <div className="flex items-center gap-3 p-3 mb-2 rounded-2xl bg-brand-ground border border-brand-border/70">
            <div className="w-10 h-10 rounded-full bg-brand-primary text-white font-bold flex items-center justify-center text-sm shadow-clinical-xs shrink-0">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-brand-text truncate">{displayName}</p>
              <p className="text-xs text-brand-muted truncate">{user?.email}</p>
            </div>
            <Badge variant="info" size="sm" className="uppercase text-[9px]">
              Doctor
            </Badge>
          </div>

          <NavLink
            to="/doctor"
            end
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/doctor/appointments"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            My Appointments
          </NavLink>
          <NavLink
            to="/doctor/queue"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            Patient Queue
          </NavLink>
          <NavLink
            to="/doctor/schedule"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            My Schedule
          </NavLink>
          <NavLink
            to="/doctor/notifications"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            <div className="flex items-center justify-between">
              <span>Notifications</span>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-clinical-danger text-white text-xs font-bold">
                  {unreadCount}
                </span>
              )}
            </div>
          </NavLink>
          <NavLink
            to="/doctor/profile"
            onClick={() => setMobileMenuOpen(false)}
            className={mobileNavLinkClass}
          >
            My Profile
          </NavLink>

          <div className="pt-3 border-t border-brand-border">
            <Button
              variant="outline"
              size="md"
              onClick={handleLogout}
              className="w-full text-xs text-brand-muted hover:text-clinical-danger hover:border-red-200 hover:bg-red-50/60 justify-center"
            >
              Sign Out
            </Button>
          </div>
        </div>
      )}
    </header>
  )
}
