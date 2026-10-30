import React from 'react'
import { Outlet } from 'react-router-dom'
import DoctorNavbar from '../components/doctor/DoctorNavbar'
import Footer from '../components/Footer'

export default function DoctorLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-brand-ground text-brand-text font-sans antialiased selection:bg-brand-mint selection:text-brand-deep">
      <DoctorNavbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
