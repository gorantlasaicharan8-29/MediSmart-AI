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
