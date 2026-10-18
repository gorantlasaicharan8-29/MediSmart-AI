import React from 'react'
import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto px-4 py-20 text-center space-y-4">
      <div className="text-6xl font-black text-teal-600">404</div>
      <h1 className="text-xl font-bold text-slate-900">Page Not Found</h1>
      <p className="text-sm text-slate-500">
        The healthcare or clinic page you requested does not exist or has moved.
      </p>
      <div className="pt-4">
        <Link
          to="/"
          className="inline-flex items-center px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold transition-colors"
        >
          Return Home
        </Link>
      </div>
    </div>
  )
}
