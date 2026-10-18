import React, { useState } from 'react'
import { Link } from 'react-router-dom'

export default function Register() {
  const [role, setRole] = useState('patient')

  const handleSubmit = (e) => {
    e.preventDefault()
    alert('User registration APIs will be connected in Phase 2 (Authentication & User Management).')
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
              <option value="patient">Patient (Book Appointments & Track Queue)</option>
              <option value="doctor">Doctor (Manage Consultations & Schedule)</option>
              <option value="hospital_admin">Hospital Admin (Manage Clinic & Facilities)</option>
              <option value="system_admin">System Admin (Full Operational Oversight)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Full Name
            </label>
            <input
              type="text"
              required
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
              placeholder="name@example.com"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Phone Number
            </label>
            <input
              type="tel"
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
              placeholder="At least 8 characters"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div className="pt-2">
            <button
              type="submit"
              className="w-full py-2.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold transition-colors shadow-sm"
            >
              Complete Registration
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
