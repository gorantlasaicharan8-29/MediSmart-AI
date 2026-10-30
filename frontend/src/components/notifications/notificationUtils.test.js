import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatRelativeTime,
  getUrgencyConfig,
  getCategoryIcon,
  getNotificationWsUrl,
} from './notificationUtils.js'

test('formatRelativeTime returns empty string for missing or invalid dates', () => {
  assert.equal(formatRelativeTime(null), '')
  assert.equal(formatRelativeTime(''), '')
  assert.equal(formatRelativeTime('not-a-date'), '')
})

test('formatRelativeTime formats recent intervals accurately', () => {
  const now = Date.now()

  // 10 seconds ago -> Just now
  const tenSecAgo = new Date(now - 10 * 1000).toISOString()
  assert.equal(formatRelativeTime(tenSecAgo), 'Just now')

  // 45 seconds ago -> 45s ago
  const fortyFiveSecAgo = new Date(now - 45 * 1000).toISOString()
  assert.equal(formatRelativeTime(fortyFiveSecAgo), '45s ago')

  // 5 minutes ago -> 5m ago
  const fiveMinAgo = new Date(now - 5 * 60 * 1000).toISOString()
  assert.equal(formatRelativeTime(fiveMinAgo), '5m ago')

  // 3 hours ago -> 3h ago
  const threeHoursAgo = new Date(now - 3 * 3600 * 1000).toISOString()
  assert.equal(formatRelativeTime(threeHoursAgo), '3h ago')

  // 26 hours ago -> Yesterday
  const yesterday = new Date(now - 26 * 3600 * 1000).toISOString()
  assert.equal(formatRelativeTime(yesterday), 'Yesterday')

  // 4 days ago -> 4d ago
  const fourDaysAgo = new Date(now - 4 * 86400 * 1000).toISOString()
  assert.equal(formatRelativeTime(fourDaysAgo), '4d ago')
})

test('getUrgencyConfig returns appropriate styling tokens and pulse rules', () => {
  const urgent = getUrgencyConfig('urgent')
  assert.equal(urgent.variant, 'danger')
  assert.equal(urgent.pulse, true)
  assert.equal(urgent.label, 'Urgent')

  const high = getUrgencyConfig('high')
  assert.equal(high.variant, 'warning')
  assert.equal(high.pulse, false)
  assert.equal(high.label, 'High Priority')

  const low = getUrgencyConfig('low')
  assert.equal(low.variant, 'neutral')
  assert.equal(low.pulse, false)

  const normal = getUrgencyConfig('normal')
  assert.equal(normal.variant, 'teal')
  assert.equal(normal.label, 'Normal')

  const fallback = getUrgencyConfig('unknown_urgency')
  assert.equal(fallback.variant, 'teal')
})

test('getCategoryIcon returns appropriate clinical icon names', () => {
  assert.equal(getCategoryIcon('queue'), 'ticket')
  assert.equal(getCategoryIcon('appointment'), 'calendar')
  assert.equal(getCategoryIcon('system'), 'info')
  assert.equal(getCategoryIcon('other'), 'info')
})

test('getNotificationWsUrl builds valid WebSocket URLs', () => {
  // SSR or non-browser environment
  const originalWindow = global.window
  delete global.window
  assert.equal(getNotificationWsUrl(), '')

  // Browser http:
  global.window = {
    location: { protocol: 'http:', host: 'localhost:5173' },
  }
  assert.equal(getNotificationWsUrl(), 'ws://localhost:5173/api/v1/notifications/ws')

  // Browser https:
  global.window = {
    location: { protocol: 'https:', host: 'medismart.ai' },
  }
  assert.equal(getNotificationWsUrl(), 'wss://medismart.ai/api/v1/notifications/ws')

  // Cleanup
  global.window = originalWindow
})

