import React from 'react'
import { Navigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-medium text-slate-500">Checking session...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto text-xl font-bold">
          ⚠️
        </div>
        <h2 className="text-xl font-bold text-slate-900">Access Restricted</h2>
        <p className="text-sm text-slate-600">
          Your account role (<span className="font-semibold text-slate-800 capitalize">{user?.role?.replace('_', ' ')}</span>) does not have permission to view this section.
        </p>
        <div className="pt-2 flex justify-center gap-3">
          <Link
            to="/"
            className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold transition-colors shadow-sm"
          >
            Return to Home
          </Link>
        </div>
      </div>
    )
  }

  return children
}
