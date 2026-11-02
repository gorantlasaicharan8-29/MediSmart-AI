const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Helper to execute fetch requests with credentials included (cookies).
 */
async function request(url, options = {}) {
  const config = {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  }

  const res = await fetch(`${API_BASE}${url}`, config)

  // Parse JSON response body if present
  let data = null
  const contentType = res.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    data = await res.json()
  }

  if (!res.ok) {
    let message = `Request failed with status ${res.status}`
    if (typeof data?.detail === 'string') {
      message = data.detail
    } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
      message = data.detail.map((e) => e.msg || e.message || String(e)).join(', ')
    } else if (res.status === 500) {
      message = 'Server connection error. Please ensure the backend server is running and try again.'
    }
    const error = new Error(message)
    error.status = res.status
    error.data = data
    throw error
  }

  return data
}

/**
 * Health check querying the FastAPI backend.
 */
export async function checkBackendHealth() {
  try {
    return await request('/api/v1/health', { method: 'GET' })
  } catch (err) {
    return { status: 'error', detail: err.message }
  }
}

/**
 * Health check verifying PostgreSQL database connectivity.
 */
export async function checkDatabaseHealth() {
  try {
    return await request('/api/v1/health/db', { method: 'GET' })
  } catch (err) {
    return { status: 'error', detail: err.message }
  }
}

/**
 * Public user registration (Patient or Doctor).
 */
export async function registerUser({ email, password, full_name, phone, role }) {
  return await request('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name, phone: phone || null, role }),
  })
}

/**
 * User login. Sets HttpOnly cookie on backend and returns user info and token.
 */
export async function loginUser({ email, password }) {
  return await request('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

/**
 * Get current authenticated user profile using active session cookie.
 */
export async function getCurrentUser() {
  return await request('/api/v1/auth/me', {
    method: 'GET',
  })
}

/**
 * Logout current user session and clear HttpOnly cookie on backend.
 */
export async function logoutUser() {
  return await request('/api/v1/auth/logout', {
    method: 'POST',
  })
}

/**
 * Fetch paginated hospitals with optional search and filters.
 */
export async function getHospitals(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  })
  const qs = query.toString()
  return await request(`/api/v1/hospitals${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  })
}

/**
 * Fetch single hospital detail by ID.
 */
export async function getHospitalById(id) {
  return await request(`/api/v1/hospitals/${id}`, {
    method: 'GET',
  })
}

/**
 * Create a new hospital facility (Hospital Admin / System Admin).
 */
export async function createHospital(data) {
  return await request('/api/v1/hospitals', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Update hospital details (Hospital Admin / System Admin).
 */
export async function updateHospital(id, data) {
  return await request(`/api/v1/hospitals/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

/**
 * Delete a hospital facility (System Admin only).
 */
export async function deleteHospital(id) {
  return await request(`/api/v1/hospitals/${id}`, {
    method: 'DELETE',
  })
}

/**
 * Fetch paginated doctors with optional search and filters.
 */
export async function getDoctors(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  })
  const qs = query.toString()
  return await request(`/api/v1/doctors${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  })
}

/**
 * Fetch doctor detail by ID.
 */
export async function getDoctorById(id) {
  return await request(`/api/v1/doctors/${id}`, {
    method: 'GET',
  })
}

/**
 * Fetch authenticated doctor profile with hospital and user details.
 */
export async function getMyDoctorProfile() {
  return await request('/api/v1/doctors/me', {
    method: 'GET',
  })
}

/**
 * Update authenticated doctor's profile (bio, availability, fee, available days).
 */
export async function updateMyDoctorProfile(data) {
  return await request('/api/v1/doctors/me', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/**
 * Fetch live authenticated doctor dashboard summary statistics.
 */
export async function getMyDoctorStats() {
  return await request('/api/v1/doctors/me/stats', {
    method: 'GET',
  })
}

/**
 * Fetch available consultation slots for a doctor on a specific date.
 */
export async function getDoctorSlots(doctorId, date) {
  return await request(`/api/v1/doctors/${doctorId}/slots?date=${encodeURIComponent(date)}`, {
    method: 'GET',
  })
}

/**
 * Book an appointment with concurrency conflict protection.
 */
export async function bookAppointment(data) {
  return await request('/api/v1/appointments', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Get appointments with role-scoped isolation.
 */
export async function getMyAppointments(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  })
  const qs = query.toString()
  return await request(`/api/v1/appointments${qs ? `?${qs}` : ''}`, {
    method: 'GET',
  })
}

export const getAppointments = getMyAppointments

/**
 * Get single appointment details by ID.
 */
export async function getAppointmentById(id) {
  return await request(`/api/v1/appointments/${id}`, {
    method: 'GET',
  })
}

/**
 * Cancel an appointment transactionally.
 */
export async function cancelAppointment(id, cancellationReason) {
  return await request(`/api/v1/appointments/${id}/cancel`, {
    method: 'POST',
    body: JSON.stringify({ cancellation_reason: cancellationReason || null }),
  })
}

/**
 * Check in an appointment into the active daily queue.
 */
export async function checkInQueue({ appointment_token, appointment_id }) {
  return await request('/api/v1/queue/check-in', {
    method: 'POST',
    body: JSON.stringify({
      appointment_token: appointment_token || null,
      appointment_id: appointment_id || null,
    }),
  })
}

/**
 * Get the current patient's active queue entry with dynamic position and wait time.
 */
export async function getMyQueueEntry() {
  return await request('/api/v1/queue/my', {
    method: 'GET',
  })
}

/**
 * Get public clinic waiting room board for a specific doctor (zero PII).
 */
export async function getDoctorPublicBoard(doctorId) {
  return await request(`/api/v1/queue/doctor/${doctorId}/public-board`, {
    method: 'GET',
  })
}

/**
 * Cancel a queue entry and its linked appointment.
 */
export async function cancelQueueEntry(entryId) {
  return await request(`/api/v1/queue/${entryId}`, {
    method: 'DELETE',
  })
}

/**
 * Get full clinical queue for authorized doctor or staff.
 */
export async function getDoctorClinicalQueue(doctorId) {
  return await request(`/api/v1/queue/doctor/${doctorId}`, {
    method: 'GET',
  })
}

/**
 * Call a waiting patient into active consultation.
 */
export async function callQueuePatient(entryId, notes = null) {
  return await request(`/api/v1/queue/${entryId}/call`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || null }),
  })
}

/**
 * Mark in-consultation patient as completed with optional clinical notes.
 */
export async function completeQueuePatient(entryId, notes = null) {
  return await request(`/api/v1/queue/${entryId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || null }),
  })
}

/**
 * Skip a waiting or in-consultation patient (marked as no-show).
 */
export async function skipQueuePatient(entryId, notes = null) {
  return await request(`/api/v1/queue/${entryId}/skip`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || null }),
  })
}

/**
 * Recall a skipped patient back into the active waiting queue.
 */
export async function recallQueuePatient(entryId, notes = null) {
  return await request(`/api/v1/queue/${entryId}/recall`, {
    method: 'POST',
    body: JSON.stringify({ notes: notes || null }),
  })
}

// ---------------------------------------------------------------------------
// Phase 6.6: Machine Learning Prediction Services
// ---------------------------------------------------------------------------

/**
 * Predict patient waiting time in minutes at clinic check-in.
 * Authenticated via HttpOnly session cookies (zero localStorage tokens).
 */
export async function predictWaitingTime(data) {
  return await request('/api/v1/predictions/waiting-time', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Predict appointment no-show probability and risk band.
 * Authenticated via HttpOnly session cookies (zero localStorage tokens).
 */
export async function predictNoShow(data) {
  return await request('/api/v1/predictions/no-show', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Check ML model service availability and metadata status.
 * Authenticated via HttpOnly session cookies.
 */
export async function getMLServiceStatus() {
  return await request('/api/v1/predictions/status', {
    method: 'GET',
  })
}

// ---------------------------------------------------------------------------
// Phase 6.4: Notification Services
// ---------------------------------------------------------------------------

/**
 * Fetch paginated notifications for current authenticated user.
 */
export async function getNotifications(params = {}, signal = null) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.append(key, value)
    }
  })
  const qs = query.toString()
  return await request(`/api/v1/notifications${qs ? `?${qs}` : ''}`, {
    method: 'GET',
    signal: signal || undefined,
  })
}

/**
 * Mark a specific notification as read.
 */
export async function markNotificationAsRead(notificationId) {
  return await request(`/api/v1/notifications/${notificationId}/read`, {
    method: 'PATCH',
  })
}

/**
 * Mark all unread notifications as read for current user.
 */
export async function markAllNotificationsAsRead() {
  return await request('/api/v1/notifications/read-all', {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// Phase 9.1: AI-Powered Doctor Recommendations
// ---------------------------------------------------------------------------

/**
 * Fetch explainable AI doctor recommendations based on patient preferences.
 * @param {Object} preferences
 * @param {string} [preferences.specialty]
 * @param {string} [preferences.city]
 * @param {string} [preferences.hospital_id]
 * @param {string} [preferences.hospital_name]
 * @param {number} [preferences.max_fee]
 * @param {string} [preferences.preferred_date]
 * @param {string} [preferences.consultation_type]
 * @param {number} [preferences.limit]
 */
export async function getDoctorRecommendations(preferences = {}) {
  return await request('/api/v1/recommendations/doctors', {
    method: 'POST',
    body: JSON.stringify(preferences),
  })
}

// ---------------------------------------------------------------------------
// Phase 9.2: Intelligent Real-Time Queue Predictions & Doctor Analytics
// ---------------------------------------------------------------------------

/**
 * Fetch authenticated patient's real-time intelligent queue waiting-time prediction.
 */
export async function getMyQueuePrediction() {
  return await request('/api/v1/predictions/queue/my', {
    method: 'GET',
  })
}

/**
 * Fetch authenticated doctor's intelligent queue analytics.
 * @param {string} [doctorId] Optional doctor ID for hospital admins / system admins.
 */
export async function getDoctorQueueAnalytics(doctorId = null) {
  const query = doctorId ? `?doctor_id=${encodeURIComponent(doctorId)}` : ''
  return await request(`/api/v1/predictions/doctor/queue-analytics${query}`, {
    method: 'GET',
  })
}

// ---------------------------------------------------------------------------
// Phase 9.3: AI Appointment No-Show Prediction & Hospital Analytics
// ---------------------------------------------------------------------------

/**
 * Fetch detailed no-show risk assessment for a specific appointment.
 * @param {string} appointmentId
 */
export async function getAppointmentNoShowRisk(appointmentId) {
  return await request(`/api/v1/predictions/appointments/${encodeURIComponent(appointmentId)}/risk`, {
    method: 'GET',
  })
}

/**
 * Fetch doctor's appointments list with no-show risk scoring and summary counts.
 * @param {Object} [params]
 * @param {string} [params.date] Filter by consultation date YYYY-MM-DD
 * @param {string} [params.risk_level] Filter by risk tier: 'all', 'low', 'medium', 'high'
 * @param {number} [params.page] Page number
 * @param {number} [params.page_size] Items per page
 * @param {string} [params.doctorId] Doctor ID (for hospital admin or system admin)
 */
export async function getDoctorAppointmentsRisk(params = {}) {
  const queryParts = []
  if (params.date) queryParts.push(`date=${encodeURIComponent(params.date)}`)
  if (params.risk_level) queryParts.push(`risk_level=${encodeURIComponent(params.risk_level)}`)
  if (params.page) queryParts.push(`page=${encodeURIComponent(params.page)}`)
  if (params.page_size) queryParts.push(`page_size=${encodeURIComponent(params.page_size)}`)
  if (params.doctorId) queryParts.push(`doctor_id=${encodeURIComponent(params.doctorId)}`)

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : ''
  return await request(`/api/v1/predictions/doctor/appointments-risk${queryString}`, {
    method: 'GET',
  })
}

/**
 * Fetch aggregate no-show analytics for hospital administrator.
 * @param {string} [hospitalId] Optional hospital ID for system admin
 */
export async function getHospitalNoShowAnalytics(hospitalId = null) {
  const query = hospitalId ? `?hospital_id=${encodeURIComponent(hospitalId)}` : ''
  return await request(`/api/v1/predictions/hospital/no-show-analytics${query}`, {
    method: 'GET',
  })
}

/**
 * Dispatch an intelligent, idempotent appointment reminder notification to patient.
 * @param {string} appointmentId
 */
export async function sendAppointmentReminder(appointmentId) {
  return await request(`/api/v1/predictions/appointments/${encodeURIComponent(appointmentId)}/send-reminder`, {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// Phase 10: Clinical Consultation Notes & Electronic Health Records (EHR)
// ---------------------------------------------------------------------------

/**
 * Physician documents or updates clinical consultation notes & digital prescriptions.
 * @param {Object} data ConsultationNoteCreate payload
 */
export async function createConsultationNote(data) {
  return await request('/api/v1/ehr/consultations', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Retrieve clinical consultation record for an appointment.
 * @param {string} appointmentId
 */
export async function getConsultationByAppointment(appointmentId) {
  return await request(`/api/v1/ehr/consultations/appointment/${encodeURIComponent(appointmentId)}`, {
    method: 'GET',
  })
}

/**
 * Retrieve clinical consultation record by note ID.
 * @param {string} consultationId
 */
export async function getConsultationById(consultationId) {
  return await request(`/api/v1/ehr/consultations/${encodeURIComponent(consultationId)}`, {
    method: 'GET',
  })
}

/**
 * Retrieve authenticated patient's own electronic health record (EHR) timeline.
 */
export async function getMyMedicalHistory() {
  return await request('/api/v1/ehr/my-history', {
    method: 'GET',
  })
}

/**
 * Retrieve patient medical history by patient ID (Treating doctor or staff).
 * @param {string} patientId
 */
export async function getPatientMedicalHistory(patientId) {
  return await request(`/api/v1/ehr/patient/${encodeURIComponent(patientId)}/history`, {
    method: 'GET',
  })
}

/**
 * Coordinate follow-up care or book follow-up appointment with patient notification.
 * @param {Object} data FollowUpCreateRequest
 */
export async function createFollowUp(data) {
  return await request('/api/v1/ehr/follow-up', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Retrieve a specific digital prescription with medication items and amendment status.
 * @param {string} prescriptionId
 */
export async function getPrescriptionById(prescriptionId) {
  return await request(`/api/v1/ehr/prescriptions/${encodeURIComponent(prescriptionId)}`, {
    method: 'GET',
  })
}

/**
 * Amend an issued digital prescription (creating a new revision and preserving audit history).
 * @param {string} prescriptionId
 * @param {Object} data PrescriptionAmendRequest
 */
export async function amendPrescription(prescriptionId, data) {
  return await request(`/api/v1/ehr/prescriptions/${encodeURIComponent(prescriptionId)}/amend`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Retrieve HIPAA/GDPR clinical audit logs for authorized entity reviews.
 * @param {Object} [params]
 */
export async function getClinicalAuditLogs(params = {}) {
  const query = new URLSearchParams()
  if (params.patient_id) query.set('patient_id', params.patient_id)
  if (params.action) query.set('action', params.action)
  if (params.limit) query.set('limit', String(params.limit))
  if (params.offset) query.set('offset', String(params.offset))
  const qs = query.toString() ? `?${query.toString()}` : ''

  return await request(`/api/v1/ehr/audit-logs${qs}`, {
    method: 'GET',
  })
}

/**
 * Clinical Decision Support System (CDSS) APIs
 */

/**
 * Perform comprehensive CDSS evaluation (summarization, completeness, Rx safety, guidelines).
 * @param {Object} payload CDSSComprehensiveRequest
 */
export async function evaluateCDSS(payload) {
  return await request('/api/v1/cdss/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Generate concise structured summary from clinical encounter notes.
 * @param {Object} notes NoteSummaryInput
 */
export async function summarizeClinicalNotes(notes) {
  return await request('/api/v1/cdss/summarize-notes', {
    method: 'POST',
    body: JSON.stringify(notes),
  })
}

/**
 * Audit clinical documentation completeness across essential sections.
 * @param {Object} notes NoteSummaryInput
 */
export async function checkDocumentationCompleteness(notes) {
  return await request('/api/v1/cdss/check-documentation', {
    method: 'POST',
    body: JSON.stringify(notes),
  })
}

/**
 * Check prescribed medications for duplicates, verified interactions, and missing instructions.
 * @param {Object} payload MedicationSafetyCheckRequest
 */
export async function checkMedicationSafety(payload) {
  return await request('/api/v1/cdss/medication-safety', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Query accredited clinical practice guidelines for documented condition.
 * @param {Object} [params]
 */
export async function getClinicalGuidelines(params = {}) {
  const query = new URLSearchParams()
  if (params.diagnosis) query.set('diagnosis', params.diagnosis)
  if (params.code) query.set('code', params.code)
  if (params.specialty) query.set('specialty', params.specialty)
  const qs = query.toString() ? `?${query.toString()}` : ''

  return await request(`/api/v1/cdss/guidelines${qs}`, {
    method: 'GET',
  })
}

/**
 * Retrieve longitudinal patient medical history insights for authorized clinicians.
 * @param {string} patientId
 */
export async function getPatientCDSSInsights(patientId) {
  return await request(`/api/v1/cdss/patient/${encodeURIComponent(patientId)}/insights`, {
    method: 'GET',
  })
}

/**
 * Retrieve CDSS knowledge base governance metadata and version information.
 */
export async function getCDSSKnowledgeBaseMetadata() {
  return await request('/api/v1/cdss/knowledge-base/metadata', {
    method: 'GET',
  })
}

/**
 * Acknowledge or dismiss a CDSS safety alert.
 * @param {Object} payload CDSSSafetyEventAcknowledgeRequest
 */
export async function acknowledgeCDSSSafetyEvent(payload) {
  return await request('/api/v1/cdss/safety-events/acknowledge', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Submit clinician feedback on CDSS evaluation accuracy.
 * @param {Object} payload CDSSFeedbackInput
 */
export async function submitCDSSFeedback(payload) {
  return await request('/api/v1/cdss/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * Retrieve clinician feedback records for QA and governance review.
 * @param {Object} [params]
 */
export async function getCDSSFeedback(params = {}) {
  const query = new URLSearchParams()
  if (params.limit) query.append('limit', params.limit)
  const qs = query.toString() ? `?${query.toString()}` : ''
  return await request(`/api/v1/cdss/feedback${qs}`, {
    method: 'GET',
  })
}

/**
 * Retrieve CDSS safety metrics, alert resolution rates, and governance trends.
 * @param {Object} [params]
 */
export async function getCDSSDashboardMetrics(params = {}) {
  const query = new URLSearchParams()
  if (params.hospital_id) query.append('hospital_id', params.hospital_id)
  if (params.severity) query.append('severity', params.severity)
  if (params.warning_category) query.append('warning_category', params.warning_category)
  if (params.start_date) query.append('start_date', params.start_date)
  if (params.end_date) query.append('end_date', params.end_date)
  const qs = query.toString() ? `?${query.toString()}` : ''
  return await request(`/api/v1/cdss/dashboard/metrics${qs}`, {
    method: 'GET',
  })
}

/**
 * Retrieve verified absolute clinical contraindications catalog.
 */
export async function getCDSSContraindications() {
  return await request('/api/v1/cdss/contraindications', {
    method: 'GET',
  })
}








