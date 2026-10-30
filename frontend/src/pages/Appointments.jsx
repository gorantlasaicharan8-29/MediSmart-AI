import React, { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppointmentCard from '../components/appointments/AppointmentCard'
import MLStatusBadge from '../components/ml/MLStatusBadge'
import {
  cancelAppointment,
  checkInQueue,
  getMyAppointments,
} from '../services/api'
import {
  Button,
  Badge,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Skeleton,
  EmptyState,
  ClinicalIcon,
} from '../components/ui'

const getTodayStr = () => new Date().toISOString().split('T')[0]

export default function Appointments() {
  const navigate = useNavigate()
  const [todayStr] = useState(getTodayStr)

  const [appointments, setAppointments] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('all') // 'all', 'scheduled', 'checked_in', 'completed', 'cancelled'
  const [reloadKey, setReloadKey] = useState(0)

  // Cancellation state
  const [appointmentToCancel, setAppointmentToCancel] = useState(null)
  const [cancellationReason, setCancellationReason] = useState('')
  const [isCancelling, setIsCancelling] = useState(false)
  const [cancellationError, setCancellationError] = useState(null)

  // Check-in state
  const [checkingInId, setCheckingInId] = useState(null)
  const [checkInSuccessData, setCheckInSuccessData] = useState(null)
  const [actionNotice, setActionNotice] = useState(null)

  const refreshAppointments = useCallback(() => {
    setIsLoading(true)
    setReloadKey((k) => k + 1)
  }, [])

  // Fetch appointments
  useEffect(() => {
    let ignore = false

    async function load() {
      try {
        const data = await getMyAppointments({ page: 1, page_size: 100 })
        if (!ignore) {
          setAppointments(data.items || [])
          setError(null)
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || 'Failed to load appointments. Please check your connection and retry.')
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    load()
    return () => {
      ignore = true
    }
  }, [reloadKey])

  // Open cancellation modal
  const handleOpenCancelModal = (appointment) => {
    setAppointmentToCancel(appointment)
    setCancellationReason('')
    setCancellationError(null)
  }

  // Confirm cancellation in modal
  const handleConfirmCancel = async () => {
    if (!appointmentToCancel) return

    setIsCancelling(true)
    setCancellationError(null)

    try {
      await cancelAppointment(appointmentToCancel.id, cancellationReason.trim() || null)
      setActionNotice({
        type: 'success',
        message: `Appointment with token ${appointmentToCancel.appointment_token} has been cancelled and the slot was released.`,
      })
      setAppointmentToCancel(null)
      refreshAppointments()
    } catch (err) {
      setCancellationError(err.message || 'Failed to cancel appointment. Please try again.')
    } finally {
      setIsCancelling(false)
    }
  }

  // Handle patient check-in
  const handleCheckIn = async (appointment) => {
    setCheckingInId(appointment.id)
    setError(null)

    try {
      const queueEntry = await checkInQueue({
        appointment_token: appointment.appointment_token,
        appointment_id: appointment.id,
      })

      setCheckInSuccessData({
        appointment,
        queueEntry,
      })

      // Update state locally so card immediately switches to checked_in
      setAppointments((prev) =>
        prev.map((a) => (a.id === appointment.id ? { ...a, status: 'checked_in' } : a))
      )
    } catch (err) {
      setActionNotice({
        type: 'error',
        message: err.message || 'Check-in failed. Please ensure your appointment is for today.',
      })
    } finally {
      setCheckingInId(null)
    }
  }

  // Filter appointments according to active tab
  const filteredAppointments = appointments.filter((appt) => {
    if (activeTab === 'all') return true
    if (activeTab === 'scheduled') return appt.status === 'scheduled'
    if (activeTab === 'checked_in') return appt.status === 'checked_in'
    if (activeTab === 'completed') return appt.status === 'completed'
    if (activeTab === 'cancelled') return appt.status === 'cancelled'
    return true
  })

  // Tab counts
  const counts = {
    all: appointments.length,
    scheduled: appointments.filter((a) => a.status === 'scheduled').length,
    checked_in: appointments.filter((a) => a.status === 'checked_in').length,
    completed: appointments.filter((a) => a.status === 'completed').length,
    cancelled: appointments.filter((a) => a.status === 'cancelled').length,
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-6 border-b border-brand-border/80">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge variant="teal" size="sm">
              <ClinicalIcon name="calendar" size={12} ariaHidden="true" />
              <span className="ml-1">Patient Appointments Dashboard</span>
            </Badge>
            <MLStatusBadge compact />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            My Consultation Appointments
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-1 max-w-2xl">
            View scheduled consultations, track unique reference tokens, self-check-in on appointment days, and manage your healthcare schedule.
          </p>
        </div>

        <Button
          variant="primary"
          size="md"
          as={Link}
          to="/doctors"
          className="shrink-0 font-bold text-xs gap-1.5 shadow-clinical-xs"
        >
          <ClinicalIcon name="stethoscope" size={14} ariaHidden="true" />
          <span>Book New Consultation</span>
        </Button>
      </div>

      {/* Global Status / Alert Banners */}
      {actionNotice && (
        <div
          role="alert"
          className={`p-4 rounded-2xl text-xs font-semibold flex items-center justify-between gap-3 ${
            actionNotice.type === 'error'
              ? 'bg-clinical-danger-bg border border-clinical-danger-border text-clinical-danger'
              : 'bg-clinical-success-bg border border-clinical-success-border text-clinical-success'
          }`}
        >
          <div className="flex items-center gap-2">
            <ClinicalIcon
              name={actionNotice.type === 'error' ? 'alert-circle' : 'check-circle'}
              size={16}
              ariaHidden="true"
            />
            <span>{actionNotice.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="p-1 rounded hover:opacity-75 transition-opacity"
            aria-label="Dismiss message"
          >
            <ClinicalIcon name="x" size={14} ariaHidden="true" />
          </button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div
          role="alert"
          className="p-4 rounded-2xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <ClinicalIcon name="alert-circle" size={16} ariaHidden="true" />
            <span>{error}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refreshAppointments}
            className="text-xs font-bold"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Category Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 border-b border-brand-border/70 no-scrollbar">
        {[
          { key: 'all', label: 'All Appointments', count: counts.all },
          { key: 'scheduled', label: 'Upcoming / Scheduled', count: counts.scheduled },
          { key: 'checked_in', label: 'In Queue', count: counts.checked_in },
          { key: 'completed', label: 'Completed', count: counts.completed },
          { key: 'cancelled', label: 'Cancelled', count: counts.cancelled },
        ].map((tab) => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer flex items-center gap-1.5 ${
                isActive
                  ? 'bg-brand-primary text-white shadow-clinical-xs'
                  : 'text-brand-muted hover:text-brand-text hover:bg-brand-ground'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-stone-200 text-brand-muted'
                }`}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Appointment Cards List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton.Card key={i} lines={4} />
          ))}
        </div>
      ) : filteredAppointments.length === 0 ? (
        <EmptyState
          icon="calendar"
          title="No Appointments Found"
          description={
            activeTab === 'all'
              ? "You haven't scheduled any doctor consultations yet. Browse specialists across affiliated hospitals to book your first appointment."
              : `You don't have any appointments matching the '${activeTab.replace('_', ' ')}' category.`
          }
          action={
            <Button
              variant="primary"
              size="md"
              as={Link}
              to="/doctors"
              className="text-xs font-bold gap-1.5"
            >
              <ClinicalIcon name="stethoscope" size={14} ariaHidden="true" />
              <span>Browse Doctors</span>
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {filteredAppointments.map((appt) => {
            // Compute real chronological prior history without inventing features
            const apptTime = new Date(appt.created_at || appt.appointment_date).getTime()
            const priorList = appointments.filter(
              (o) =>
                o.id !== appt.id &&
                new Date(o.created_at || o.appointment_date).getTime() < apptTime
            )
            const priorCount = priorList.length
            const priorNoShows = priorList.filter((a) => a.status === 'no_show').length
            const priorRate = priorCount > 0 ? priorNoShows / priorCount : 0.0

            return (
              <AppointmentCard
                key={appt.id}
                appointment={appt}
                onCancel={handleOpenCancelModal}
                onCheckIn={handleCheckIn}
                isCancelling={isCancelling && appointmentToCancel?.id === appt.id}
                isCheckingIn={checkingInId === appt.id}
                priorStats={{ priorCount, priorNoShows, priorRate }}
                todayStr={todayStr}
              />
            )
          })}
        </div>
      )}

      {/* ============================================================ */}
      {/* CANCELLATION CONFIRMATION MODAL (Step 6)                      */}
      {/* ============================================================ */}
      <Modal
        isOpen={!!appointmentToCancel}
        onClose={() => !isCancelling && setAppointmentToCancel(null)}
        size="md"
        showCloseButton={false}
      >
        <ModalHeader
          onClose={() => !isCancelling && setAppointmentToCancel(null)}
          showCloseButton={!isCancelling}
        >
          <div className="space-y-1">
            <Badge variant="danger" size="sm">
              <ClinicalIcon name="alert-triangle" size={12} ariaHidden="true" />
              <span className="ml-1">Cancellation Confirmation</span>
            </Badge>
            <h2 className="text-base font-bold text-brand-text">
              Cancel Doctor Consultation
            </h2>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-4">
          {cancellationError && (
            <div
              role="alert"
              className="p-3 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-center gap-2"
            >
              <ClinicalIcon name="alert-circle" size={14} ariaHidden="true" />
              <span>{cancellationError}</span>
            </div>
          )}

          {appointmentToCancel && (
            <div className="bg-brand-ground p-3.5 rounded-xl border border-brand-border text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-brand-muted">Doctor:</span>
                <span className="font-bold text-brand-text">
                  {appointmentToCancel.doctor?.user?.full_name || 'Doctor'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-brand-muted">Specialty:</span>
                <span className="font-medium text-brand-text">
                  {appointmentToCancel.doctor?.specialty}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-brand-muted">Date & Time:</span>
                <span className="font-bold text-brand-primary">
                  {appointmentToCancel.appointment_date} at {appointmentToCancel.appointment_time}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-brand-muted">Token:</span>
                <span className="font-mono font-bold text-brand-text">
                  {appointmentToCancel.appointment_token}
                </span>
              </div>
            </div>
          )}

          <div className="p-3 rounded-xl bg-clinical-warning-bg border border-clinical-warning-border text-xs text-clinical-warning leading-relaxed">
            <strong>Important:</strong> Cancelling this appointment will immediately release your reserved time slot for other patients. This action cannot be undone.
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="cancellation-reason-input"
              className="block text-xs font-bold text-brand-text uppercase tracking-wider"
            >
              Reason for Cancellation (Optional)
            </label>
            <input
              id="cancellation-reason-input"
              type="text"
              value={cancellationReason}
              onChange={(e) => setCancellationReason(e.target.value)}
              placeholder="e.g., schedule conflict, resolved, feeling better..."
              maxLength={500}
              className="w-full px-3.5 py-2 rounded-xl border border-brand-border bg-brand-surface text-xs text-brand-text placeholder-brand-muted focus:outline-none focus:ring-2 focus:ring-brand-accent/20 focus:border-brand-accent"
            />
          </div>
        </ModalBody>

        <ModalFooter>
          <Button
            variant="ghost"
            size="md"
            disabled={isCancelling}
            onClick={() => setAppointmentToCancel(null)}
            className="text-xs font-semibold"
          >
            Keep Appointment
          </Button>
          <Button
            variant="danger"
            size="md"
            onClick={handleConfirmCancel}
            isLoading={isCancelling}
            className="text-xs font-bold"
          >
            Confirm Cancellation
          </Button>
        </ModalFooter>
      </Modal>

      {/* ============================================================ */}
      {/* CHECK-IN SUCCESS MODAL (Step 5)                               */}
      {/* ============================================================ */}
      <Modal
        isOpen={!!checkInSuccessData}
        onClose={() => setCheckInSuccessData(null)}
        size="md"
        showCloseButton={false}
      >
        <ModalHeader onClose={() => setCheckInSuccessData(null)} showCloseButton={true}>
          <div className="space-y-1">
            <Badge variant="success" size="sm">
              <ClinicalIcon name="check-circle" size={12} ariaHidden="true" />
              <span className="ml-1">Check-in Confirmed</span>
            </Badge>
            <h2 className="text-base font-bold text-brand-text">
              Checked In to Hospital Queue
            </h2>
          </div>
        </ModalHeader>

        <ModalBody className="space-y-4 text-center py-2">
          <div className="w-14 h-14 rounded-2xl bg-clinical-success-bg text-clinical-success flex items-center justify-center mx-auto shadow-clinical-xs border border-emerald-200">
            <ClinicalIcon name="ticket" size={32} ariaHidden="true" />
          </div>

          <div className="space-y-1">
            <h3 className="text-lg font-bold text-brand-text">
              You Are Now in the Clinic Queue
            </h3>
            <p className="text-xs text-brand-muted max-w-sm mx-auto">
              Your appointment check-in has been logged. A sequential queue token has been assigned to your consultation.
            </p>
          </div>

          {checkInSuccessData?.queueEntry && (
            <div className="bg-brand-ground p-4 rounded-2xl border border-brand-border space-y-2">
              <span className="text-[10px] font-bold text-brand-muted uppercase tracking-widest block">
                Assigned Daily Queue Token
              </span>
              <div className="font-mono text-3xl font-extrabold text-brand-primary">
                #{checkInSuccessData.queueEntry.token_number}
              </div>
              {typeof checkInSuccessData.queueEntry.estimated_waiting_time_minutes === 'number' && (
                <p className="text-xs text-brand-muted">
                  Estimated waiting time:{' '}
                  <span className="font-bold text-brand-text">
                    ~{checkInSuccessData.queueEntry.estimated_waiting_time_minutes} minutes
                  </span>
                </p>
              )}
            </div>
          )}

          <div className="text-xs text-brand-muted bg-brand-surface p-3 rounded-xl border border-brand-border text-left space-y-1">
            <div className="flex justify-between">
              <span>Doctor:</span>
              <span className="font-semibold text-brand-text">
                {checkInSuccessData?.appointment?.doctor?.user?.full_name || 'Doctor'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Hospital:</span>
              <span className="font-semibold text-brand-text">
                {checkInSuccessData?.appointment?.hospital?.name || 'Hospital'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Reference Token:</span>
              <span className="font-mono font-bold text-brand-text">
                {checkInSuccessData?.appointment?.appointment_token}
              </span>
            </div>
          </div>
        </ModalBody>

        <ModalFooter>
          <Button
            variant="ghost"
            size="md"
            onClick={() => setCheckInSuccessData(null)}
            className="text-xs font-semibold"
          >
            Stay on Appointments
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => {
              setCheckInSuccessData(null)
              navigate('/queue')
            }}
            className="text-xs font-bold gap-1.5"
          >
            <ClinicalIcon name="waiting-time" size={14} ariaHidden="true" />
            <span>Go to Live Queue Tracker</span>
          </Button>
        </ModalFooter>
      </Modal>
    </div>
  )
}
