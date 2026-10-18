const API_BASE = import.meta.env.VITE_API_URL || ''

/**
 * Health check querying the FastAPI backend.
 */
export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health`)
    if (!res.ok) {
      return { status: 'error', detail: `HTTP ${res.status}` }
    }
    return await res.json()
  } catch (err) {
    return { status: 'error', detail: err.message }
  }
}

/**
 * Health check verifying PostgreSQL database connectivity.
 */
export async function checkDatabaseHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health/db`)
    if (!res.ok) {
      return { status: 'error', detail: `HTTP ${res.status}` }
    }
    return await res.json()
  } catch (err) {
    return { status: 'error', detail: err.message }
  }
}
