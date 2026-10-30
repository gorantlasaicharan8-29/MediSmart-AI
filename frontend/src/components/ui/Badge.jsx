import React from 'react'

const variantStyles = {
  teal: 'bg-teal-50 text-brand-deep border-teal-200/80',
  mint: 'bg-brand-mint text-brand-deep border-teal-300/80',
  success: 'bg-clinical-success-bg text-clinical-success border-clinical-success-border',
  warning: 'bg-clinical-warning-bg text-clinical-warning border-clinical-warning-border',
  danger: 'bg-clinical-danger-bg text-clinical-danger border-clinical-danger-border',
  info: 'bg-clinical-info-bg text-clinical-info border-clinical-info-border',
  neutral: 'bg-brand-ground text-brand-muted border-brand-border',
}

const dotColors = {
  teal: 'bg-brand-primary',
  mint: 'bg-brand-accent',
  success: 'bg-clinical-success',
  warning: 'bg-clinical-warning',
  danger: 'bg-clinical-danger',
  info: 'bg-clinical-info',
  neutral: 'bg-brand-muted',
}

const sizeStyles = {
  sm: 'text-[10px] px-2 py-0.5 rounded-full gap-1 font-semibold tracking-wide',
  md: 'text-xs px-2.5 py-1 rounded-full gap-1.5 font-medium',
  lg: 'text-sm px-3 py-1.5 rounded-full gap-2 font-semibold',
}

export default function Badge({
  children,
  variant = 'teal',
  size = 'md',
  dot = false,
  pulseDot = false,
  icon = null,
  className = '',
  ...props
}) {
  const appliedVariant = variantStyles[variant] || variantStyles.teal
  const appliedSize = sizeStyles[size] || sizeStyles.md
  const dotColorClass = dotColors[variant] || dotColors.teal

  return (
    <span
      className={`inline-flex items-center border font-sans select-none ${appliedVariant} ${appliedSize} ${className}`.trim()}
      {...props}
    >
      {dot && (
        <span className="relative flex h-2 w-2 shrink-0 items-center justify-center">
          {pulseDot && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${dotColorClass}`}
            />
          )}
          <span
            className={`relative inline-flex h-1.5 w-1.5 rounded-full ${dotColorClass}`}
          />
        </span>
      )}
      {icon && (
        <span className="inline-flex shrink-0 items-center justify-center">
          {icon}
        </span>
      )}
      <span>{children}</span>
    </span>
  )
}
