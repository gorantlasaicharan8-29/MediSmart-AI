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
    const error = new Error(data?.detail || `Request failed with status ${res.status}`)
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

