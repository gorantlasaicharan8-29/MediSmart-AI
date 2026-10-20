import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import MainLayout from './layouts/MainLayout'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import Hospitals from './pages/Hospitals'
import Doctors from './pages/Doctors'
import Appointments from './pages/Appointments'
import Queue from './pages/Queue'
import Login from './pages/Login'
import Register from './pages/Register'
import NotFound from './pages/NotFound'
import WaitingRoomMonitor from './components/queue/WaitingRoomMonitor'
import DoctorQueueConsole from './components/queue/DoctorQueueConsole'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
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
          {/* Standalone Kiosk/TV Wall Monitor Displays (Zero PII, Fullscreen) */}
          <Route path="queue/monitor" element={<WaitingRoomMonitor standalone />} />
          <Route path="queue/monitor/:doctorId" element={<WaitingRoomMonitor standalone />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
