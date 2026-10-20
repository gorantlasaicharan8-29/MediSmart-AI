import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Builds WebSocket URL pointing to the doctor's queue channel.
 */
function getWebSocketUrl(doctorId) {
  if (typeof window === 'undefined') return ''
  const explicitWs = import.meta.env.VITE_WS_URL
  if (explicitWs) {
    return `${explicitWs.replace(/\/$/, '')}/api/v1/queue/ws/${doctorId}`
  }

  const explicitApi = import.meta.env.VITE_API_URL
  if (explicitApi) {
    const wsProto = explicitApi.startsWith('https') ? 'wss:' : 'ws:'
    const host = explicitApi.replace(/^https?:\/\//, '').replace(/\/$/, '')
    return `${wsProto}//${host}/api/v1/queue/ws/${doctorId}`
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/queue/ws/${doctorId}`
}

/**
 * Custom React hook for live queue updates.
 * - Connects to WebSocket /api/v1/queue/ws/{doctorId}
 * - Automatically falls back to periodic HTTP polling (10s) if WebSocket is unavailable or disconnects.
 * - Exposes connection mode: 'live' (WS) | 'polling' (HTTP fallback) | 'reconnecting' | 'disconnected'
 */
export function useQueueSocket({
  doctorId,
  fetcher,
  enabled = true,
  pollingInterval = 10000,
  onEvent,
}) {
  const [data, setData] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [connectionMode, setConnectionMode] = useState('connecting')
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const [lastEvent, setLastEvent] = useState(null)

  const isMountedRef = useRef(true)
  const socketRef = useRef(null)
  const retryCountRef = useRef(0)
  const reconnectTimeoutRef = useRef(null)
  const pollingTimerRef = useRef(null)
  const fetcherRef = useRef(fetcher)
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    fetcherRef.current = fetcher
    onEventRef.current = onEvent
  }, [fetcher, onEvent])

  // Primary data fetcher
  const loadData = useCallback(async (isInitial = false) => {
    if (!fetcherRef.current) return
    if (isInitial && isMountedRef.current) {
      setIsLoading(true)
    }
    try {
      const result = await fetcherRef.current()
      if (isMountedRef.current) {
        setData(result)
        setError(null)
        setLastRefreshed(new Date())
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err.message || 'Failed to refresh queue data')
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [])

  // Manual refresh trigger
  const refresh = useCallback(() => {
    return loadData(false)
  }, [loadData])

  // Initial load
  useEffect(() => {
    isMountedRef.current = true
    if (enabled) {
      loadData(true)
    }
    return () => {
      isMountedRef.current = false
    }
  }, [enabled, loadData, doctorId])

  // Polling management: active whenever not in 'live' WebSocket mode
  useEffect(() => {
    if (!enabled) return

    // Clear any previous polling timer
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }

    if (connectionMode !== 'live') {
      pollingTimerRef.current = setInterval(() => {
        if (isMountedRef.current) {
          loadData(false)
        }
      }, pollingInterval)
    }

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current)
        pollingTimerRef.current = null
      }
    }
  }, [enabled, connectionMode, pollingInterval, loadData])

  // WebSocket lifecycle
  useEffect(() => {
    if (!enabled || !doctorId) {
      return
    }

    let isCancelled = false

    const connectWebSocket = () => {
      if (isCancelled || !isMountedRef.current) return

      try {
        const wsUrl = getWebSocketUrl(doctorId)
        if (!wsUrl) return

        setConnectionMode((prev) => (prev === 'live' ? 'reconnecting' : 'connecting'))

        const ws = new WebSocket(wsUrl)
        socketRef.current = ws

        ws.onopen = () => {
          if (!isMountedRef.current || isCancelled) {
            ws.close()
            return
          }
          retryCountRef.current = 0
          setConnectionMode('live')
          // Refresh state immediately upon connection to ensure synchronization
          loadData(false)
        }

        ws.onmessage = (event) => {
          if (!isMountedRef.current || isCancelled) return
          try {
            const parsed = JSON.parse(event.data)
            setLastEvent(parsed)
            if (onEventRef.current) {
              onEventRef.current(parsed)
            }
            // Trigger server refresh on queue state update
            loadData(false)
          } catch {
            // Non-JSON message (e.g. ping/pong keepalive)
          }
        }

        ws.onerror = () => {
          if (!isMountedRef.current || isCancelled) return
          setConnectionMode('polling')
        }

        ws.onclose = (event) => {
          if (!isMountedRef.current || isCancelled) return
          setConnectionMode('polling')

          // If closed normally (e.g. 1000) or deliberate navigation, don't aggressive retry
          if (event.code !== 1000) {
            const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 15000)
            retryCountRef.current += 1
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay)
          }
        }
      } catch {
        if (isMountedRef.current) {
          setConnectionMode('polling')
        }
      }
    }

    connectWebSocket()

    return () => {
      isCancelled = true
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (socketRef.current) {
        try {
          socketRef.current.close(1000, 'Component unmounted')
        } catch {}
        socketRef.current = null
      }
    }
  }, [enabled, doctorId, loadData])

  return {
    data,
    isLoading,
    error,
    isLive: connectionMode === 'live',
    connectionMode,
    lastRefreshed,
    lastEvent,
    refresh,
  }
}
