import React from 'react'
import ClinicalIcon from './ClinicalIcon'

export default function EmptyState({
  icon = 'hospital',
  title = 'No records found',
  description = 'There are currently no items matching your criteria. Try adjusting your search or filters.',
  action = null,
  secondaryAction = null,
  className = '',
}) {
  return (
    <div
      className={`text-center py-12 px-6 rounded-2xl border border-dashed border-brand-border bg-brand-ground/50 max-w-lg mx-auto my-4 space-y-4 ${className}`.trim()}
    >
      <div className="w-14 h-14 rounded-2xl bg-brand-mint/60 border border-teal-200/60 text-brand-primary flex items-center justify-center mx-auto shadow-clinical-xs">
        {typeof icon === 'string' ? (
          <ClinicalIcon name={icon} size={28} ariaHidden="true" />
        ) : (
          icon
        )}
      </div>

      <div className="space-y-1.5">
        <h3 className="text-base font-bold text-brand-text">{title}</h3>
        {description && (
          <p className="text-xs text-brand-muted max-w-sm mx-auto leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {(action || secondaryAction) && (
        <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  )
}
