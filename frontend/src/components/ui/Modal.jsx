import React, { useEffect, useRef, useId, useCallback } from 'react'
import ClinicalIcon from './ClinicalIcon'

const sizeStyles = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-6xl',
}

export function ModalHeader({
  children,
  title,
  subtitle,
  onClose,
  showCloseButton = true,
  className = '',
  titleId,
  subtitleId,
}) {
  return (
    <div
      className={`px-6 py-4.5 border-b border-brand-border/70 flex items-start justify-between gap-4 bg-brand-surface ${className}`.trim()}
    >
      <div className="space-y-0.5 min-w-0 flex-1">
        {title && (
          <h2
            id={titleId}
            className="text-base font-bold text-brand-text truncate"
          >
            {title}
          </h2>
        )}
        {subtitle && (
          <p
            id={subtitleId}
            className="text-xs text-brand-muted"
          >
            {subtitle}
          </p>
        )}
        {children}
      </div>

      {showCloseButton && onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close dialog"
          className="shrink-0 -mr-1.5 -mt-1 p-2 rounded-lg text-brand-muted hover:text-brand-text hover:bg-brand-ground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer"
        >
          <ClinicalIcon name="x" size={18} ariaHidden="true" />
        </button>
      )}
    </div>
  )
}

export function ModalBody({ children, className = '' }) {
  return (
    <div
      className={`p-6 max-h-[calc(85vh-130px)] overflow-y-auto overscroll-contain text-sm text-brand-text ${className}`.trim()}
    >
      {children}
    </div>
  )
}

export function ModalFooter({ children, className = '' }) {
  return (
    <div
      className={`px-6 py-4 bg-brand-ground/60 border-t border-brand-border/70 flex items-center justify-end gap-3 rounded-b-2xl ${className}`.trim()}
    >
      {children}
    </div>
  )
}

export default function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  size = 'md',
  closeOnEscape = true,
  closeOnBackdropClick = true,
  showCloseButton = true,
  className = '',
  initialFocusRef = null,
}) {
  const generatedId = useId()
  const titleId = `modal-title-${generatedId}`
  const subtitleId = `modal-subtitle-${generatedId}`

  const modalRef = useRef(null)
  const previousActiveElementRef = useRef(null)

  // Handle ESC key
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Escape' && closeOnEscape && onClose) {
        e.stopPropagation()
        onClose()
        return
      }

      // Focus trap
      if (e.key === 'Tab' && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (focusableElements.length === 0) return

        const firstElement = focusableElements[0]
        const lastElement = focusableElements[focusableElements.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault()
            lastElement.focus()
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault()
            firstElement.focus()
          }
        }
      }
    },
    [closeOnEscape, onClose]
  )

  useEffect(() => {
    if (!isOpen) return

    // Save previous active element for restoration on close
    previousActiveElementRef.current = document.activeElement

    // Prevent body scroll
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Add keydown listener
    window.addEventListener('keydown', handleKeyDown)

    // Focus initial element or modal
    const timer = setTimeout(() => {
      if (initialFocusRef?.current) {
        initialFocusRef.current.focus()
      } else if (modalRef.current) {
        const firstFocusable = modalRef.current.querySelector(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
        if (firstFocusable) {
          firstFocusable.focus()
        } else {
          modalRef.current.focus()
        }
      }
    }, 50)

    return () => {
      clearTimeout(timer)
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', handleKeyDown)

      // Restore focus
      if (
        previousActiveElementRef.current &&
        typeof previousActiveElementRef.current.focus === 'function'
      ) {
        previousActiveElementRef.current.focus()
      }
    }
  }, [isOpen, handleKeyDown, initialFocusRef])

  if (!isOpen) return null

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && closeOnBackdropClick && onClose) {
      onClose()
    }
  }

  const appliedSize = sizeStyles[size] || sizeStyles.md

  return (
    <div
      role="presentation"
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-brand-deep/50 backdrop-blur-xs transition-opacity duration-200"
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={subtitle ? subtitleId : undefined}
        tabIndex={-1}
        className={`w-full ${appliedSize} bg-brand-surface rounded-2xl shadow-clinical-lg border border-brand-border/80 outline-none transform transition-all duration-200 flex flex-col ${className}`.trim()}
      >
        {(title || showCloseButton) && (
          <ModalHeader
            title={title}
            subtitle={subtitle}
            onClose={onClose}
            showCloseButton={showCloseButton}
            titleId={titleId}
            subtitleId={subtitleId}
          />
        )}
        {children}
      </div>
    </div>
  )
}
