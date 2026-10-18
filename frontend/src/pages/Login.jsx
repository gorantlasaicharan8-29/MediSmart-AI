import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Notification from previous redirects (e.g. registration success)
  const successMessage = location.state?.message

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)

    try {
      await login({ email: email.trim(), password })
      // Navigate to intended page or home
      const destination = location.state?.from?.pathname || '/'
      navigate(destination, { replace: true })
    } catch (err) {
      if (err.status === 401) {
        setErrorMessage('Invalid email or password. Please check your credentials and try again.')
      } else if (err.status === 403) {
        setErrorMessage('This account is inactive or suspended. Please contact support.')
      } else {
        setErrorMessage(err.message || 'An unexpected error occurred during sign in. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-4 py-12 sm:py-16">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-xl font-bold">
            🔒
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Sign In to MediSmart</h1>
          <p className="text-xs text-slate-500">
            Enter your credentials to access your clinical dashboard
          </p>
        </div>

        {/* Success Banner */}
        {successMessage && (
          <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2.5">
            <span className="font-bold text-emerald-600">✓</span>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Banner */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2.5">
            <span className="font-bold text-rose-600">⚠️</span>
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-slate-700">
                Password
              </label>
              <span className="text-xs text-teal-600 hover:underline cursor-pointer">
                Forgot password?
              </span>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-[11px] text-slate-500 flex items-center gap-2">
            <span className="text-teal-600 font-bold">ℹ</span>
            <span>Role permissions (Patient, Doctor, Admin) are automatically verified by backend RBAC.</span>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white text-sm font-semibold transition-colors shadow-sm flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Signing in...</span>
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="text-center pt-2 text-xs text-slate-500">
          Don't have an account?{' '}
          <Link to="/register" className="text-teal-600 font-semibold hover:underline">
            Register here
          </Link>
        </div>
      </div>
    </div>
  )
}
