import React from 'react'
import { Navigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { Button, ClinicalIcon } from './ui'

export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-3 border-brand-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-medium text-brand-muted">Verifying secure session...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-clinical-warning-bg border border-clinical-warning-border text-clinical-warning flex items-center justify-center mx-auto shadow-clinical-xs">
          <ClinicalIcon name="shield-check" size={24} ariaHidden="true" />
        </div>
        <h2 className="text-xl font-bold text-brand-text">Access Restricted</h2>
        <p className="text-xs sm:text-sm text-brand-muted leading-relaxed">
          Your account role (<span className="font-semibold text-brand-text capitalize">{user?.role?.replace('_', ' ')}</span>) does not have clinical privileges to access this area.
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <Button
            variant="primary"
            size="md"
            as={Link}
            to="/"
            className="text-xs font-semibold gap-1.5"
          >
            <ClinicalIcon name="arrow-right" size={14} ariaHidden="true" />
            <span>Return to Home</span>
          </Button>
        </div>
      </div>
    )
  }

  return children
}
