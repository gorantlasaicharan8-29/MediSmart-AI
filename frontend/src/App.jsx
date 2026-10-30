import React, { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/ProtectedRoute'
import { LogoIntro } from './components/intro'
import Home from './pages/Home'

// Route-level code splitting for secondary pages
const Hospitals = lazy(() => import('./pages/Hospitals'))
const Doctors = lazy(() => import('./pages/Doctors'))
const Appointments = lazy(() => import('./pages/Appointments'))
const Queue = lazy(() => import('./pages/Queue'))
const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const NotFound = lazy(() => import('./pages/NotFound'))
const WaitingRoomMonitor = lazy(() => import('./components/queue/WaitingRoomMonitor'))
const DoctorQueueConsole = lazy(() => import('./components/queue/DoctorQueueConsole'))

// Doctor Dedicated Workspace Pages
const DoctorLayout = lazy(() => import('./layouts/DoctorLayout'))
const DoctorDashboard = lazy(() => import('./pages/doctor/DoctorDashboard'))
const DoctorAppointments = lazy(() => import('./pages/doctor/DoctorAppointments'))
const DoctorQueue = lazy(() => import('./pages/doctor/DoctorQueue'))
const DoctorSchedule = lazy(() => import('./pages/doctor/DoctorSchedule'))
const DoctorNotifications = lazy(() => import('./pages/doctor/DoctorNotifications'))
const DoctorProfile = lazy(() => import('./pages/doctor/DoctorProfile'))

function PageFallback() {
  return (
    <div className="min-h-[55vh] flex flex-col items-center justify-center space-y-3">
      <div className="w-8 h-8 border-3 border-brand-primary border-t-transparent rounded-full animate-spin" />
      <span className="text-xs font-semibold text-brand-muted">Loading MediSmart...</span>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <LogoIntro />
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {/* Standard Main Layout (Patient & Public Views) */}
            <Route path="/" element={<MainLayout />}>
              <Route index element={<Home />} />
              <Route path="hospitals" element={<Hospitals />} />
              <Route path="doctors" element={<Doctors />} />
              <Route
                path="appointments"
                element={
                  <ProtectedRoute>
                    <Appointments />
                  </ProtectedRoute>
                }
              />
              <Route path="queue" element={<Queue />} />
              <Route
                path="queue/doctor"
                element={
                  <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'system_admin']}>
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                      <DoctorQueueConsole />
                    </div>
                  </ProtectedRoute>
                }
              />
              <Route
                path="queue/doctor/:doctorId"
                element={
                  <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'system_admin']}>
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                      <DoctorQueueConsole />
                    </div>
                  </ProtectedRoute>
                }
              />
              <Route path="login" element={<Login />} />
              <Route path="register" element={<Register />} />
              <Route path="*" element={<NotFound />} />
            </Route>

            {/* Dedicated Authenticated Doctor Workspace (Clinical UI & Doctor Navbar) */}
            <Route
              path="/doctor"
              element={
                <ProtectedRoute allowedRoles={['doctor', 'hospital_admin', 'system_admin']}>
                  <DoctorLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DoctorDashboard />} />
              <Route path="appointments" element={<DoctorAppointments />} />
              <Route path="queue" element={<DoctorQueue />} />
              <Route path="schedule" element={<DoctorSchedule />} />
              <Route path="notifications" element={<DoctorNotifications />} />
              <Route path="profile" element={<DoctorProfile />} />
            </Route>

            {/* Standalone Kiosk/TV Wall Monitor Displays (Zero PII, Fullscreen) */}
            <Route path="queue/monitor" element={<WaitingRoomMonitor standalone />} />
            <Route path="queue/monitor/:doctorId" element={<WaitingRoomMonitor standalone />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}
