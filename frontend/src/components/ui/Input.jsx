import React, { forwardRef, useId } from 'react'
import ClinicalIcon from './ClinicalIcon'

const Input = forwardRef(function Input(
  {
    label,
    id: explicitId,
    name,
    type = 'text',
    error,
    helperText,
    leftIcon = null,
    rightIcon = null,
    required = false,
    disabled = false,
    className = '',
    containerClassName = '',
    ...props
  },
  ref
) {
  const generatedId = useId()
  const inputId = explicitId || generatedId
  const errorId = `${inputId}-error`
  const helperId = `${inputId}-helper`

  const hasError = Boolean(error)
  const describedBy = [
    hasError ? errorId : null,
    helperText ? helperId : null,
  ]
    .filter(Boolean)
    .join(' ')

  const baseInputClasses =
    'w-full bg-brand-surface text-brand-text placeholder:text-brand-muted/60 text-sm rounded-xl border transition-all duration-150 focus:outline-none focus:ring-2 disabled:bg-brand-ground disabled:text-brand-muted/70 disabled:cursor-not-allowed'

  const stateClasses = hasError
    ? 'border-clinical-danger text-clinical-danger focus:border-clinical-danger focus:ring-red-100'
    : 'border-brand-border hover:border-brand-muted/40 focus:border-brand-accent focus:ring-brand-mint/60'

  const paddingLeft = leftIcon ? 'pl-10' : 'pl-3.5'
  const paddingRight = rightIcon ? 'pr-10' : 'pr-3.5'
  const heightClass = 'h-10'

  return (
    <div className={`w-full space-y-1.5 ${containerClassName}`.trim()}>
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-semibold text-brand-text select-none"
        >
          {label}
          {required && (
            <span
              className="text-clinical-danger ml-1"
              aria-hidden="true"
            >
              *
            </span>
          )}
        </label>
      )}

      <div className="relative flex items-center">
        {leftIcon && (
          <div
            className="absolute left-3 flex items-center justify-center pointer-events-none text-brand-muted"
            aria-hidden="true"
          >
            {leftIcon}
          </div>
        )}

        <input
          ref={ref}
          id={inputId}
          name={name}
          type={type}
          disabled={disabled}
          required={required}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={describedBy || undefined}
          className={`${baseInputClasses} ${stateClasses} ${paddingLeft} ${paddingRight} ${heightClass} ${className}`.trim()}
          {...props}
        />

        {rightIcon && (
          <div className="absolute right-3 flex items-center justify-center text-brand-muted">
            {rightIcon}
          </div>
        )}
      </div>

      {hasError ? (
        <p
          id={errorId}
          role="alert"
          className="text-xs font-medium text-clinical-danger flex items-center gap-1.5 pt-0.5"
        >
          <ClinicalIcon
            name="alert-circle"
            size={14}
            className="shrink-0 text-clinical-danger"
            ariaHidden="true"
          />
          <span>{error}</span>
        </p>
      ) : helperText ? (
        <p
          id={helperId}
          className="text-xs text-brand-muted pt-0.5"
        >
          {helperText}
        </p>
      ) : null}
    </div>
  )
})

export default Input
