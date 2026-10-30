import React, { forwardRef, useId } from 'react'
import ClinicalIcon from './ClinicalIcon'

const Select = forwardRef(function Select(
  {
    label,
    id: explicitId,
    name,
    children,
    error,
    helperText,
    leftIcon = null,
    required = false,
    disabled = false,
    placeholder = null,
    className = '',
    containerClassName = '',
    value,
    defaultValue,
    onChange,
    ...props
  },
  ref
) {
  const generatedId = useId()
  const selectId = explicitId || generatedId
  const errorId = `${selectId}-error`
  const helperId = `${selectId}-helper`

  const hasError = Boolean(error)
  const describedBy = [
    hasError ? errorId : null,
    helperText ? helperId : null,
  ]
    .filter(Boolean)
    .join(' ')

  const baseSelectClasses =
    'w-full appearance-none bg-brand-surface text-brand-text text-sm rounded-xl border transition-all duration-150 focus:outline-none focus:ring-2 disabled:bg-brand-ground disabled:text-brand-muted/70 disabled:cursor-not-allowed cursor-pointer'

  const stateClasses = hasError
    ? 'border-clinical-danger text-clinical-danger focus:border-clinical-danger focus:ring-red-100'
    : 'border-brand-border hover:border-brand-muted/40 focus:border-brand-accent focus:ring-brand-mint/60'

  const paddingLeft = leftIcon ? 'pl-10' : 'pl-3.5'
  const paddingRight = 'pr-10'
  const heightClass = 'h-10'

  return (
    <div className={`w-full space-y-1.5 ${containerClassName}`.trim()}>
      {label && (
        <label
          htmlFor={selectId}
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

        <select
          ref={ref}
          id={selectId}
          name={name}
          disabled={disabled}
          required={required}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={describedBy || undefined}
          value={value}
          defaultValue={defaultValue}
          onChange={onChange}
          className={`${baseSelectClasses} ${stateClasses} ${paddingLeft} ${paddingRight} ${heightClass} ${className}`.trim()}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {children}
        </select>

        <div
          className="absolute right-3 flex items-center justify-center pointer-events-none text-brand-muted"
          aria-hidden="true"
        >
          <ClinicalIcon
            name="chevron-down"
            size={16}
            ariaHidden="true"
          />
        </div>
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

export default Select
