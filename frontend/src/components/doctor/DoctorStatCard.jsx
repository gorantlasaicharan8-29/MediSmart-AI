import React from 'react'
import { ClinicalIcon, Skeleton } from '../ui'

export default function DoctorStatCard({
  title,
  value,
  subtitle,
  icon,
  accentColor = 'teal',
  isLoading = false,
  badgeText,
}) {
  const getAccentStyles = () => {
    switch (accentColor) {
      case 'teal':
        return {
          iconBg: 'bg-brand-mint text-brand-deep border-teal-200/80',
          borderHover: 'hover:border-brand-primary',
          indicator: 'bg-brand-primary',
        }
      case 'amber':
        return {
          iconBg: 'bg-amber-50 text-amber-700 border-amber-200/80',
          borderHover: 'hover:border-amber-400',
          indicator: 'bg-amber-500',
        }
      case 'emerald':
        return {
          iconBg: 'bg-emerald-50 text-emerald-700 border-emerald-200/80',
          borderHover: 'hover:border-emerald-400',
          indicator: 'bg-emerald-500',
        }
      case 'cyan':
      default:
        return {
          iconBg: 'bg-cyan-50 text-cyan-800 border-cyan-200/80',
          borderHover: 'hover:border-cyan-400',
          indicator: 'bg-cyan-600',
        }
    }
  }

  const styles = getAccentStyles()

  return (
    <div
      className={`relative bg-brand-surface rounded-2xl sm:rounded-3xl border border-brand-border p-5 sm:p-6 shadow-clinical-xs transition-all duration-200 ${styles.borderHover} overflow-hidden`}
    >
      {/* Top Accent Strip */}
      <div className={`absolute top-0 left-0 right-0 h-1 ${styles.indicator}`} />

      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1.5 flex-1 min-w-0">
          <p className="text-xs font-bold text-brand-muted uppercase tracking-wider truncate">
            {title}
          </p>
          {isLoading ? (
            <div className="py-1">
              <Skeleton className="h-9 w-20 rounded-lg" />
            </div>
          ) : (
            <p className="text-2xl sm:text-3xl font-extrabold text-brand-text tracking-tight truncate">
              {value}
            </p>
          )}
          <p className="text-xs text-brand-muted truncate font-medium">
            {subtitle}
          </p>
        </div>

        <div
          className={`w-12 h-12 rounded-2xl flex items-center justify-center border shadow-clinical-xs shrink-0 ${styles.iconBg}`}
        >
          <ClinicalIcon name={icon} size={22} ariaHidden="true" />
        </div>
      </div>

      {badgeText && (
        <div className="mt-3 pt-3 border-t border-brand-border/60 flex items-center justify-between text-[11px] font-semibold text-brand-muted">
          <span>{badgeText}</span>
        </div>
      )}
    </div>
  )
}
