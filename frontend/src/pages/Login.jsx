import React, { useState } from 'react'
import { Link } from 'react-router-dom'

export default function Login() {
  const [selectedRole, setSelectedRole] = useState('patient')

  const roles = [
    { id: 'patient', label: 'Patient' },
    { id: 'doctor', label: 'Doctor' },
    { id: 'hospital_admin', label: 'Hospital Admin' },
    { id: 'system_admin', label: 'System Admin' },
  ]

  const handleSubmit = (e) => {
    e.preventDefault()
    alert('Authentication APIs will be connected in Phase 2 (Authentication & User Management).')
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
            Select your account role and enter your credentials
          </p>
        </div>

        {/* Role Selector Tabs */}
        <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl">
          {roles.map((role) => (
            <button
              key={role.id}
              type="button"
              onClick={() => setSelectedRole(role.id)}
              className={`py-2 text-xs font-semibold rounded-lg transition-all ${
                selectedRole === role.id
                  ? 'bg-white text-slate-900 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {role.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
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
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600 bg-white"
            />
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-[11px] text-slate-500 flex items-center gap-2">
            <span className="text-teal-600 font-bold">ℹ</span>
            <span>Signing in as <strong className="text-slate-800">{roles.find(r => r.id === selectedRole)?.label}</strong></span>
          </div>

          <button
            type="submit"
            className="w-full py-2.5 px-4 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold transition-colors shadow-sm"
          >
            Sign In
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
