import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function Register() {
  const [role, setRole] = useState('patient')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters in length.')
      return
    }

    setIsSubmitting(true)

    try {
      await register({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        phone: phone.trim() || null,
        role,
      })

      // Redirect to login with success notice
      navigate('/login', {
        state: {
          message: 'Account created successfully! Please sign in with your email and password.',
        },
      })
    } catch (err) {
      if (err.status === 409) {
        setErrorMessage('An account with this email address already exists. Please sign in or use another email.')
      } else if (err.status === 403) {
        setErrorMessage('Administrative roles cannot be self-assigned. Contact your system administrator.')
      } else {
        setErrorMessage(err.message || 'An error occurred during registration. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-12 sm:py-16">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mx-auto text-xl font-bold">
            👤
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Create your MediSmart Account</h1>
          <p className="text-xs text-slate-500">
            Join the digital healthcare and queue management platform
          </p>
        </div>

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
              Select Account Type
            </label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            >
              <option value="patient">Patient (Book Appointments & Track Live Queue)</option>
              <option value="doctor">Doctor (Consultations & Schedule Management)</option>
            </select>
          </div>

          {/* Admin role callout */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-[11px] text-slate-500">
            <span className="font-semibold text-slate-700">Notice: </span>
            Hospital Admin and System Admin accounts are provisioned directly by administrative staff and cannot be created via public registration.
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Full Name
            </label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Dr. John Doe or Jane Smith"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

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
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Phone Number <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 (555) 000-0000"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white text-sm font-semibold transition-colors shadow-sm flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                'Complete Registration'
              )}
            </button>
          </div>
        </form>

        <div className="text-center pt-2 text-xs text-slate-500">
          Already registered?{' '}
          <Link to="/login" className="text-teal-600 font-semibold hover:underline">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  )
}
