/**
 * Healthcare-friendly relative time formatter for notification timestamps.
 */
export function formatRelativeTime(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return ''

  const now = new Date()
  const diffInSeconds = Math.floor((now - date) / 1000)

  if (diffInSeconds < 30) return 'Just now'
  if (diffInSeconds < 60) return `${diffInSeconds}s ago`
  const diffInMinutes = Math.floor(diffInSeconds / 60)
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`
  const diffInHours = Math.floor(diffInMinutes / 60)
  if (diffInHours < 24) return `${diffInHours}h ago`
  const diffInDays = Math.floor(diffInHours / 24)
  if (diffInDays === 1) return 'Yesterday'
  if (diffInDays < 7) return `${diffInDays}d ago`

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: now.getFullYear() !== date.getFullYear() ? 'numeric' : undefined,
  })
}

/**
 * Returns icon and badge styling per notification urgency.
 */
export function getUrgencyConfig(urgency) {
  switch (urgency) {
    case 'urgent':
      return {
        variant: 'danger',
        label: 'Urgent',
        pulse: true,
        borderClass: 'border-l-clinical-danger',
      }
    case 'high':
      return {
        variant: 'warning',
        label: 'High Priority',
        pulse: false,
        borderClass: 'border-l-clinical-warning',
      }
    case 'low':
      return {
        variant: 'neutral',
        label: 'Low',
        pulse: false,
        borderClass: 'border-l-brand-border',
      }
    default:
      return {
        variant: 'teal',
        label: 'Normal',
        pulse: false,
        borderClass: 'border-l-brand-accent',
      }
  }
}

/**
 * Returns icon per notification category.
 */
export function getCategoryIcon(category) {
  switch (category) {
    case 'queue':
      return 'ticket'
    case 'appointment':
      return 'calendar'
    default:
      return 'info'
  }
}

/**
 * Resolves the authenticated notification WebSocket endpoint URL.
 */
export function getNotificationWsUrl() {
  if (typeof window === 'undefined') return ''
  const explicitWs = import.meta.env?.VITE_WS_URL
  if (explicitWs) {
    return `${explicitWs.replace(/\/$/, '')}/api/v1/notifications/ws`
  }

  const explicitApi = import.meta.env?.VITE_API_URL
  if (explicitApi) {
    const wsProto = explicitApi.startsWith('https') ? 'wss:' : 'ws:'
    const host = explicitApi.replace(/^https?:\/\//, '').replace(/\/$/, '')
    return `${wsProto}//${host}/api/v1/notifications/ws`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/notifications/ws`
}

