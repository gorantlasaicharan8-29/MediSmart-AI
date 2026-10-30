import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../../context/useAuth'
import {
  getNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
} from '../../services/api'
import { Badge, Button, ClinicalIcon, EmptyState, Skeleton } from '../ui'
import {
  formatRelativeTime,
  getUrgencyConfig,
  getCategoryIcon,
  getNotificationWsUrl,
} from './notificationUtils'

export default function NotificationCenter() {
  const { user, isAuthenticated } = useAuth()

  const [isOpen, setIsOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifications, setNotifications] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [filterUnread, setFilterUnread] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [isMarkingAll, setIsMarkingAll] = useState(false)
  const [error, setError] = useState(null)

  const containerRef = useRef(null)
  const triggerButtonRef = useRef(null)
  const abortControllerRef = useRef(null)
  const socketRef = useRef(null)
  const retryCountRef = useRef(0)
  const reconnectTimeoutRef = useRef(null)
  const previousUserIdRef = useRef(user?.id)

  // ---------------------------------------------------------------------------
  // User Session Change Reset
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (previousUserIdRef.current !== user?.id) {
      previousUserIdRef.current = user?.id
      setNotifications([])
      setUnreadCount(0)
      setTotalCount(0)
      setError(null)
    }
  }, [user])

  // ---------------------------------------------------------------------------
  // Real-Time WebSocket Notification Delivery
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isAuthenticated || !user) {
      if (socketRef.current) {
        try {
          socketRef.current.close(1000, 'User logged out')
        } catch {}
        socketRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      return
    }

    let isCancelled = false

    const connectWebSocket = () => {
      if (isCancelled) return

      const wsUrl = getNotificationWsUrl()
      if (!wsUrl) return

      try {
        const ws = new WebSocket(wsUrl)
        socketRef.current = ws

        ws.onopen = () => {
          if (isCancelled) {
            try {
              ws.close(1000, 'Component unmounted')
            } catch {}
            return
          }
          retryCountRef.current = 0
        }

        ws.onmessage = (event) => {
          if (isCancelled) return
          try {
            const data = JSON.parse(event.data)
            if (data?.event === 'NOTIFICATION_CREATED' && data?.notification) {
              const incoming = data.notification
              // 1. Increment unread counter badge
              setUnreadCount((prev) => prev + 1)

              // 2. Safely merge into current notifications list without duplicates
              setNotifications((prev) => {
                if (prev.some((item) => item.id === incoming.id)) {
                  return prev
                }
                return [incoming, ...prev]
              })
              setTotalCount((prev) => prev + 1)
            }
          } catch {
            // Heartbeats or non-JSON payloads safely ignored
          }
        }

        ws.onerror = () => {
          // Socket error will lead to onclose; fallback polling handles sync
        }

        ws.onclose = (event) => {
          if (isCancelled) return

          // Bounded exponential backoff reconnection if not closed normally (1000)
          if (event.code !== 1000) {
            const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 30000)
            retryCountRef.current += 1
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay)
          }
        }
      } catch {
        // Fallback polling covers network or protocol instantiation failures
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
          socketRef.current.close(1000, 'NotificationCenter unmounted')
        } catch {}
        socketRef.current = null
      }
    }
  }, [isAuthenticated, user])

  // ---------------------------------------------------------------------------
  // Polling Fallback & Count Sync (Every 30s)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isAuthenticated || !user) return

    let ignore = false

    const poll = async () => {
      try {
        const data = await getNotifications({ limit: 1 })
        if (!ignore && typeof data?.unread_count === 'number') {
          setUnreadCount(data.unread_count)
        }
      } catch {
        // Fail silently for background unread poll
      }
    }

    poll()
    const timer = setInterval(poll, 30000)

    return () => {
      ignore = true
      clearInterval(timer)
    }
  }, [isAuthenticated, user])

  // ---------------------------------------------------------------------------
  // Fetch Notification List
  // ---------------------------------------------------------------------------

  const fetchNotificationList = useCallback(
    async (offset = 0, isAppend = false, unreadOnly = filterUnread) => {
      if (!isAuthenticated || !user) return

      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      const controller = new AbortController()
      abortControllerRef.current = controller

      if (isAppend) {
        setIsLoadingMore(true)
      } else {
        setIsLoading(true)
      }
      setError(null)

      try {
        const params = {
          limit: 15,
          offset,
        }
        if (unreadOnly) {
          params.is_read = false
        }

        const data = await getNotifications(params, controller.signal)

        if (typeof data?.unread_count === 'number') {
          setUnreadCount(data.unread_count)
        }
        setTotalCount(data?.total || 0)

        if (isAppend) {
          setNotifications((prev) => [...prev, ...(data?.items || [])])
        } else {
          setNotifications(data?.items || [])
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load notifications')
        }
      } finally {
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    },
    [isAuthenticated, user, filterUnread]
  )

  // ---------------------------------------------------------------------------
  // Keyboard Navigation & Click-Outside Handling
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!isOpen) return

    const handleClickOutside = (event) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
        triggerButtonRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('touchstart', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('touchstart', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  // ---------------------------------------------------------------------------
  // Action Handlers
  // ---------------------------------------------------------------------------

  const handleToggleOpen = () => {
    const nextState = !isOpen
    setIsOpen(nextState)
    if (nextState) {
      fetchNotificationList(0, false, filterUnread)
    }
  }

  const handleFilterToggle = (unreadOnly) => {
    if (filterUnread === unreadOnly) return
    setFilterUnread(unreadOnly)
    fetchNotificationList(0, false, unreadOnly)
  }

  const handleMarkAsRead = async (notificationId, event) => {
    event?.stopPropagation()
    try {
      await markNotificationAsRead(notificationId)
      // Optimistic local update
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notificationId
            ? { ...n, is_read: true, read_at: new Date().toISOString() }
            : n
        )
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    } catch (err) {
      setError(err.message || 'Failed to mark notification as read')
    }
  }

  const handleMarkAllAsRead = async () => {
    if (unreadCount === 0 || isMarkingAll) return

    setIsMarkingAll(true)
    setError(null)
    try {
      await markAllNotificationsAsRead()
      // Optimistic update
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
      )
      setUnreadCount(0)
      if (filterUnread) {
        setNotifications([])
        setTotalCount(0)
      }
    } catch (err) {
      setError(err.message || 'Failed to mark all as read')
    } finally {
      setIsMarkingAll(false)
    }
  }

  const handleLoadMore = () => {
    fetchNotificationList(notifications.length, true, filterUnread)
  }

  if (!isAuthenticated || !user) {
    return null
  }

  const hasMore = notifications.length < totalCount
  const displayBadgeCount = unreadCount > 99 ? '99+' : unreadCount

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      {/* Bell Trigger Button */}
      <button
        ref={triggerButtonRef}
        type="button"
        onClick={handleToggleOpen}
        className={`relative p-2 rounded-xl text-brand-muted hover:text-brand-text hover:bg-brand-ground transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer select-none ${
          isOpen ? 'bg-brand-ground text-brand-deep shadow-clinical-xs' : ''
        }`}
        aria-label={
          unreadCount > 0
            ? `Notifications, ${unreadCount} unread`
            : 'Notifications'
        }
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        <ClinicalIcon
          name="bell"
          size={20}
          className={`transition-transform duration-200 ${
            unreadCount > 0 ? 'text-brand-deep' : 'text-brand-muted'
          }`}
          ariaHidden="true"
        />

        {/* Unread Counter Badge */}
        {unreadCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-5 h-5 px-1 rounded-full bg-brand-primary text-[10px] font-bold text-white border-2 border-brand-surface shadow-clinical-xs animate-in fade-in zoom-in-75 duration-150"
            aria-hidden="true"
          >
            {displayBadgeCount}
          </span>
        )}
      </button>

      {/* Popover Drawer / Dropdown */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Notification center"
          aria-modal="false"
          className="absolute right-0 sm:right-0 mt-2 w-[calc(100vw-2rem)] sm:w-[420px] max-w-[420px] rounded-2xl bg-brand-surface border border-brand-border shadow-clinical-lg z-50 overflow-hidden flex flex-col max-h-[560px] animate-in fade-in slide-in-from-top-2 duration-150"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border/80 bg-brand-surface sticky top-0 z-10">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-brand-text">Notifications</h2>
              {unreadCount > 0 && (
                <Badge variant="teal" size="sm">
                  {unreadCount} unread
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-1.5">
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleMarkAllAsRead}
                  disabled={isMarkingAll}
                  className="text-xs text-brand-accent hover:text-brand-deep px-2 py-1 h-auto font-medium"
                >
                  {isMarkingAll ? (
                    <ClinicalIcon name="spinner" size={13} className="mr-1" />
                  ) : (
                    <ClinicalIcon name="check" size={13} className="mr-1" />
                  )}
                  Mark all read
                </Button>
              )}

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-lg text-brand-muted hover:text-brand-text hover:bg-brand-ground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer"
                aria-label="Close notification panel"
              >
                <ClinicalIcon name="x" size={16} ariaHidden="true" />
              </button>
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-2 px-4 py-2 border-b border-brand-border/50 bg-brand-ground/40 text-xs">
            <button
              type="button"
              onClick={() => handleFilterToggle(false)}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all cursor-pointer select-none ${
                !filterUnread
                  ? 'bg-brand-surface text-brand-deep shadow-clinical-xs border border-brand-border'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => handleFilterToggle(true)}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all cursor-pointer select-none flex items-center gap-1 ${
                filterUnread
                  ? 'bg-brand-surface text-brand-deep shadow-clinical-xs border border-brand-border'
                  : 'text-brand-muted hover:text-brand-text'
              }`}
            >
              <span>Unread</span>
              {unreadCount > 0 && (
                <span className="w-1.5 h-1.5 rounded-full bg-brand-accent" />
              )}
            </button>
          </div>

          {/* Content Body */}
          <div className="flex-1 overflow-y-auto divide-y divide-brand-border/40 focus:outline-none">
            {error && (
              <div className="p-4 bg-clinical-danger-bg text-clinical-danger border-b border-clinical-danger-border flex items-start gap-2 text-xs">
                <ClinicalIcon name="alert-circle" size={16} className="shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold">Unable to sync notifications</p>
                  <p className="text-[11px] opacity-90 mt-0.5">{error}</p>
                </div>
                <button
                  type="button"
                  onClick={() => fetchNotificationList(0, false, filterUnread)}
                  className="font-bold underline ml-2 cursor-pointer hover:opacity-80"
                >
                  Retry
                </button>
              </div>
            )}

            {isLoading ? (
              <div className="p-4 space-y-3">
                <div className="p-3 rounded-xl border border-brand-border/60 bg-brand-ground/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-4 w-32 rounded-md" />
                    <Skeleton className="h-3 w-16 rounded-md" />
                  </div>
                  <Skeleton className="h-3 w-full rounded-md" />
                  <Skeleton className="h-3 w-3/4 rounded-md" />
                </div>
                <div className="p-3 rounded-xl border border-brand-border/60 bg-brand-ground/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-4 w-28 rounded-md" />
                    <Skeleton className="h-3 w-14 rounded-md" />
                  </div>
                  <Skeleton className="h-3 w-full rounded-md" />
                  <Skeleton className="h-3 w-2/3 rounded-md" />
                </div>
              </div>
            ) : notifications.length === 0 ? (
              <EmptyState
                icon="bell"
                title={filterUnread ? 'No unread notifications' : 'All caught up'}
                description={
                  filterUnread
                    ? 'You have read all your clinical and queue updates.'
                    : 'No notifications at this time. Future appointment confirmations and queue alerts will appear here.'
                }
                className="my-6 border-none bg-transparent"
              />
            ) : (
              notifications.map((notif) => {
                const urgencyCfg = getUrgencyConfig(notif.urgency)
                const categoryIcon = getCategoryIcon(notif.category)
                const isUnread = !notif.is_read

                return (
                  <article
                    key={notif.id}
                    className={`p-3.5 sm:p-4 transition-colors duration-150 relative ${
                      isUnread
                        ? `bg-brand-mint/15 border-l-4 ${urgencyCfg.borderClass}`
                        : 'bg-brand-surface hover:bg-brand-ground/40 border-l-4 border-l-transparent'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Icon */}
                      <div
                        className={`w-8 h-8 rounded-xl shrink-0 flex items-center justify-center shadow-clinical-xs mt-0.5 ${
                          isUnread
                            ? 'bg-brand-surface border border-teal-200 text-brand-primary'
                            : 'bg-brand-ground border border-brand-border text-brand-muted'
                        }`}
                      >
                        <ClinicalIcon name={categoryIcon} size={16} ariaHidden="true" />
                      </div>

                      {/* Text details */}
                      <div className="flex-1 min-w-0 pr-1">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <h3
                            className={`text-xs truncate ${
                              isUnread
                                ? 'font-bold text-brand-text'
                                : 'font-medium text-brand-text/90'
                            }`}
                          >
                            {notif.title}
                          </h3>
                          <time
                            dateTime={notif.created_at}
                            className="text-[10px] text-brand-muted shrink-0"
                          >
                            {formatRelativeTime(notif.created_at)}
                          </time>
                        </div>

                        <p className="text-xs text-brand-muted leading-relaxed mb-2 break-words">
                          {notif.message}
                        </p>

                        <div className="flex items-center justify-between gap-2 pt-1 border-t border-brand-border/30">
                          <div className="flex items-center gap-1.5">
                            <Badge
                              variant={urgencyCfg.variant}
                              size="sm"
                              dot={isUnread}
                              pulseDot={urgencyCfg.pulse && isUnread}
                              className="text-[9px] py-0 px-1.5 uppercase tracking-wider"
                            >
                              {urgencyCfg.label}
                            </Badge>
                            <span className="text-[10px] text-brand-muted/80 capitalize">
                              {notif.category}
                            </span>
                          </div>

                          {isUnread && (
                            <button
                              type="button"
                              onClick={(e) => handleMarkAsRead(notif.id, e)}
                              className="text-[11px] font-semibold text-brand-accent hover:text-brand-deep focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent rounded px-1.5 py-0.5 cursor-pointer select-none inline-flex items-center gap-1"
                              aria-label={`Mark "${notif.title}" as read`}
                            >
                              <ClinicalIcon name="check" size={12} ariaHidden="true" />
                              <span>Mark read</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </article>
                )
              })
            )}

            {/* Load More Button */}
            {!isLoading && hasMore && (
              <div className="p-3 text-center bg-brand-ground/30">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLoadMore}
                  disabled={isLoadingMore}
                  className="w-full text-xs font-semibold text-brand-muted hover:text-brand-text"
                >
                  {isLoadingMore ? (
                    <>
                      <ClinicalIcon name="spinner" size={14} className="mr-1.5" />
                      Loading...
                    </>
                  ) : (
                    'Load earlier updates'
                  )}
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

