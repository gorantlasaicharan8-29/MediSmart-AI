import React from 'react'
import { Badge, Button, ClinicalIcon } from '../ui'

export default function HospitalCard({
  hospital,
  isSelected = false,
  onSelect = () => {},
  onViewDetails = () => {},
}) {
  const hasCoords = hospital.latitude !== null && hospital.longitude !== null

  return (
    <div
      onClick={() => onSelect(hospital)}
      tabIndex={0}
      role="button"
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(hospital)
        }
      }}
      className={`p-5 rounded-2xl border transition-all cursor-pointer bg-brand-surface outline-none focus-visible:ring-2 focus-visible:ring-brand-accent ${
        isSelected
          ? 'border-brand-primary ring-2 ring-brand-mint shadow-clinical-sm'
          : 'border-brand-border hover:border-brand-muted/40 hover:shadow-clinical-xs'
      }`}
    >
      <div className="space-y-3">
        {/* Status Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge
            variant={hospital.data_source === 'verified' ? 'teal' : 'neutral'}
            size="sm"
          >
            {hospital.data_source === 'verified' ? 'Verified Facility' : 'Sample Record'}
          </Badge>

          <Badge
            variant={hasCoords ? 'mint' : 'neutral'}
            size="sm"
            icon={
              <ClinicalIcon
                name={hasCoords ? 'map-pin' : 'alert-circle'}
                size={12}
                ariaHidden="true"
              />
            }
          >
            {hasCoords ? 'GPS Mapped' : 'Location Pending'}
          </Badge>
        </div>

        {/* Title & Location */}
        <div>
          <h3 className="text-base font-bold text-brand-text group-hover:text-brand-deep transition-colors">
            {hospital.name}
          </h3>
          <p className="text-xs text-brand-muted mt-1 leading-relaxed">
            {hospital.address},{' '}
            <span className="font-semibold text-brand-text">
              {hospital.city}
            </span>
            , {hospital.state}
          </p>
        </div>

        {/* Specialties */}
        {hospital.specialties && hospital.specialties.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {hospital.specialties.slice(0, 4).map((spec, idx) => (
              <span
                key={idx}
                className="text-[11px] font-medium px-2 py-0.5 rounded-lg bg-brand-ground text-brand-muted border border-brand-border/70"
              >
                {spec}
              </span>
            ))}
            {hospital.specialties.length > 4 && (
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-lg bg-brand-ground text-brand-muted/70">
                +{hospital.specialties.length - 4} more
              </span>
            )}
          </div>
        )}

        {/* Contact & Actions */}
        <div className="pt-3 border-t border-brand-border/70 flex items-center justify-between text-xs text-brand-muted">
          <div className="flex items-center gap-2">
            {hospital.phone ? (
              <span className="font-medium text-brand-text flex items-center gap-1.5">
                <ClinicalIcon
                  name="heart-pulse"
                  size={14}
                  className="text-brand-accent"
                  ariaHidden="true"
                />
                <span className="truncate max-w-[150px]">{hospital.phone}</span>
              </span>
            ) : (
              <span className="text-[11px] text-brand-muted/70">
                {hospital.city}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {hasCoords && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  onSelect(hospital)
                }}
                className="text-xs text-brand-muted hover:text-brand-deep"
              >
                Pin on Map
              </Button>
            )}
            <Button
              variant="secondary"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onViewDetails(hospital)
              }}
              className="text-xs font-semibold"
            >
              Details &rarr;
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
