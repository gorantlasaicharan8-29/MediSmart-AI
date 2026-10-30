import React, { forwardRef } from 'react'
import ClinicalIcon from './ClinicalIcon'

const variantStyles = {
  primary:
    'bg-brand-primary text-white hover:bg-brand-deep active:bg-brand-deep/95 shadow-clinical-sm border border-brand-primary focus-visible:ring-brand-accent',
  secondary:
    'bg-brand-mint text-brand-deep hover:bg-teal-200/70 active:bg-teal-200 border border-teal-200/80 shadow-clinical-xs focus-visible:ring-brand-accent',
  outline:
    'bg-brand-surface text-brand-text hover:bg-brand-ground hover:border-brand-muted/40 active:bg-stone-100 border border-brand-border shadow-clinical-xs focus-visible:ring-brand-accent',
  danger:
    'bg-clinical-danger text-white hover:bg-red-800 active:bg-red-900 border border-clinical-danger shadow-clinical-sm focus-visible:ring-red-500',
  ghost:
    'bg-transparent text-brand-text hover:bg-brand-ground hover:text-brand-deep active:bg-brand-mint/40 border border-transparent focus-visible:ring-brand-accent',
  link:
    'bg-transparent text-brand-accent hover:text-brand-deep active:text-brand-deep underline-offset-4 hover:underline border-0 p-0 h-auto shadow-none focus-visible:ring-brand-accent',
}

const sizeStyles = {
  sm: 'text-xs px-2.5 py-1.5 rounded-lg gap-1.5 min-h-[32px]',
  md: 'text-sm px-4 py-2 rounded-xl gap-2 min-h-[40px]',
  lg: 'text-base px-5 py-2.5 rounded-xl gap-2.5 min-h-[46px] font-semibold',
  icon: 'p-2 rounded-xl min-h-[36px] min-w-[36px] justify-center',
}

const Button = forwardRef(function Button(
  {
    children,
    variant = 'primary',
    size = 'md',
    type = 'button',
    disabled = false,
    isLoading = false,
    leftIcon = null,
    rightIcon = null,
    className = '',
    onClick,
    as: Component = 'button',
    ...props
  },
  ref
) {
  const isActionDisabled = disabled || isLoading
  const isLinkVariant = variant === 'link'

  const baseClasses =
    'inline-flex items-center justify-center font-medium transition-all duration-150 select-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2'

  const disabledClasses = isActionDisabled
    ? 'opacity-55 cursor-not-allowed pointer-events-none shadow-none'
    : 'active:scale-[0.99]'

  const appliedVariant = variantStyles[variant] || variantStyles.primary
  const appliedSize = isLinkVariant ? '' : sizeStyles[size] || sizeStyles.md

  const combinedClassName = [
    baseClasses,
    appliedVariant,
    appliedSize,
    disabledClasses,
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const buttonProps = Component === 'button' ? { type } : {}

  return (
    <Component
      ref={ref}
      {...buttonProps}
      disabled={Component === 'button' ? isActionDisabled : undefined}
      aria-disabled={isActionDisabled ? 'true' : undefined}
      aria-busy={isLoading ? 'true' : undefined}
      onClick={isActionDisabled ? undefined : onClick}
      className={combinedClassName}
      {...props}
    >
      {isLoading ? (
        <>
          <ClinicalIcon
            name="spinner"
            size={size === 'sm' ? 14 : size === 'lg' ? 18 : 16}
            ariaHidden="false"
            title="Loading"
            className="animate-spin text-current"
          />
          {!isLinkVariant && size !== 'icon' && <span>{children}</span>}
        </>
      ) : (
        <>
          {leftIcon && (
            <span className="inline-flex shrink-0 items-center justify-center">
              {leftIcon}
            </span>
          )}
          {children}
          {rightIcon && (
            <span className="inline-flex shrink-0 items-center justify-center">
              {rightIcon}
            </span>
          )}
        </>
      )}
    </Component>
  )
})

export default Button
