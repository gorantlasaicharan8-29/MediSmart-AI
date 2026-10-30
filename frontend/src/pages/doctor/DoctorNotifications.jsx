import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  getNotifications,
  markNotificationAsRead,
  markAllNotificationsAsRead,
} from '../../services/api'
import {
  formatRelativeTime,
  getUrgencyConfig,
  getCategoryIcon,
  getNotificationWsUrl,
} from '../../components/notifications/notificationUtils'
import { Button, Badge, ClinicalIcon, EmptyState, Skeleton } from '../../components/ui'

export default function DoctorNotifications() {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [filterUnread, setFilterUnread] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isMarkingAll, setIsMarkingAll] = useState(false)
  const socketRef = useRef(null)

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getNotifications({
        limit: 50,
        unread_only: filterUnread,
      })
      setNotifications(data.items || [])
      setUnreadCount(data.unread_count ?? 0)
    } catch (err) {
      setError(err.message || 'Failed to load notifications')
    } finally {
      setIsLoading(false)
    }
  }, [filterUnread])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  // Setup WebSocket for live notifications
  useEffect(() => {
    const wsUrl = getNotificationWsUrl()
    if (!wsUrl) return

    try {
      const ws = new WebSocket(wsUrl)
      socketRef.current = ws

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'notification' && payload.notification) {
            setNotifications((prev) => [payload.notification, ...prev])
            setUnreadCount((prev) => prev + 1)
          }
        } catch {}
      }
    } catch {}

    return () => {
      if (socketRef.current) {
        try {
          socketRef.current.close(1000, 'Unmounting notifications page')
        } catch {}
      }
    }
  }, [])

  // Mark a single notification as read
  const handleMarkAsRead = async (id, isRead) => {
    if (isRead) return
    try {
      await markNotificationAsRead(id)
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      setUnreadCount((prev) => Math.max(0, prev - 1))
    } catch {}
  }

  // Mark all as read
  const handleMarkAllRead = async () => {
    setIsMarkingAll(true)
    try {
      await markAllNotificationsAsRead()
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch (err) {
      setError(err.message || 'Failed to mark all as read')
    } finally {
      setIsMarkingAll(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-brand-border/70">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-brand-primary" />
            <span className="text-xs font-bold text-brand-primary uppercase tracking-wider">
              Clinical Alerts &amp; Updates
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight">
            Doctor Notifications
          </h1>
          <p className="text-xs sm:text-sm text-brand-muted mt-0.5">
            Stay informed on appointment bookings, queue check-ins, and schedule changes
          </p>
        </div>

        {/* Header Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {unreadCount > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleMarkAllRead}
              disabled={isMarkingAll}
              className="text-xs text-brand-primary border-brand-primary/40 hover:bg-brand-mint/40"
            >
              <ClinicalIcon name="check" size={14} className="mr-1.5" />
              {isMarkingAll ? 'Marking...' : 'Mark All Read'}
            </Button>
          )}

          <Button
            size="sm"
            variant="outline"
            onClick={fetchNotifications}
            className="text-xs"
          >
            <ClinicalIcon name="activity" size={14} className="mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between">
        <div className="inline-flex p-1 rounded-2xl bg-brand-ground border border-brand-border">
          <button
            type="button"
            onClick={() => setFilterUnread(false)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              !filterUnread
                ? 'bg-white text-brand-text shadow-xs'
                : 'text-brand-muted hover:text-brand-text'
            }`}
          >
            All Updates
          </button>
          <button
            type="button"
            onClick={() => setFilterUnread(true)}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
              filterUnread
                ? 'bg-white text-brand-text shadow-xs'
                : 'text-brand-muted hover:text-brand-text'
            }`}
          >
            Unread
            {unreadCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-brand-accent text-white font-bold">
                {unreadCount}
              </span>
            )}
          </button>
        </div>

        <span className="text-xs text-brand-muted font-medium">
          {notifications.length} notification{notifications.length === 1 ? '' : 's'}
        </span>
      </div>

      {/* Notifications List */}
      <div className="bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-4 sm:p-6 shadow-clinical-xs">
        {isLoading ? (
          <div className="space-y-4 py-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex gap-4 p-4 border border-brand-border/60 rounded-2xl">
                <Skeleton className="w-10 h-10 rounded-xl shrink-0" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-1/3 rounded" />
                  <Skeleton className="h-3 w-3/4 rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="p-8 text-center space-y-3">
            <ClinicalIcon name="alert" size={24} className="text-red-500 mx-auto" />
            <p className="text-xs text-red-700">{error}</p>
            <Button size="sm" variant="outline" onClick={fetchNotifications}>
              Retry Loading
            </Button>
          </div>
        ) : notifications.length === 0 ? (
          <EmptyState
            title="No Notifications"
            description={
              filterUnread
                ? 'You are all caught up! No unread notifications right now.'
                : 'No notification records currently available for your account.'
            }
          />
        ) : (
          <div className="divide-y divide-brand-border/60 space-y-1">
            {notifications.map((item) => {
              const urgency = getUrgencyConfig(item.urgency)
              const iconName = getCategoryIcon(item.category)

              return (
                <div
                  key={item.id}
                  onClick={() => handleMarkAsRead(item.id, item.is_read)}
                  className={`p-4 rounded-2xl transition-all cursor-pointer flex items-start gap-4 ${
                    !item.is_read
                      ? 'bg-teal-50/40 hover:bg-teal-50/70 border-l-4 border-brand-primary'
                      : 'hover:bg-brand-ground/50'
                  }`}
                >
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                      !item.is_read
                        ? 'bg-brand-mint text-brand-deep'
                        : 'bg-brand-ground text-brand-muted'
                    }`}
                  >
                    <ClinicalIcon name={iconName} size={18} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-brand-text truncate">
                          {item.title}
                        </span>
                        {!item.is_read && (
                          <span className="w-2 h-2 rounded-full bg-brand-primary" />
                        )}
                      </div>
                      <span className="text-[11px] text-brand-muted shrink-0 font-medium">
                        {formatRelativeTime(item.created_at)}
                      </span>
                    </div>

                    <p className="text-xs text-brand-text/80 leading-relaxed mb-2">
                      {item.message}
                    </p>

                    <div className="flex items-center gap-2">
                      <Badge variant={urgency.variant} size="sm">
                        {urgency.label}
                      </Badge>
                      {item.category && (
                        <span className="text-[10px] uppercase font-bold text-brand-muted tracking-wider">
                          {item.category}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
