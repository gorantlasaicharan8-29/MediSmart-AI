import React from 'react'

export function SkeletonLine({
  width = 'w-full',
  height = 'h-4',
  className = '',
}) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-stone-200/70 ${width} ${height} ${className}`.trim()}
    />
  )
}

export function SkeletonCircle({ size = 'h-10 w-10', className = '' }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-full bg-stone-200/70 shrink-0 ${size} ${className}`.trim()}
    />
  )
}

export function SkeletonButton({
  width = 'w-24',
  height = 'h-10',
  className = '',
}) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-xl bg-stone-200/70 ${width} ${height} ${className}`.trim()}
    />
  )
}

export function SkeletonCard({ className = '', lines = 3 }) {
  return (
    <div
      aria-hidden="true"
      className={`p-5 rounded-2xl bg-brand-surface border border-brand-border/70 space-y-4 shadow-clinical-xs ${className}`.trim()}
    >
      <div className="flex items-center gap-3">
        <SkeletonCircle size="h-10 w-10" />
        <div className="space-y-1.5 flex-1">
          <SkeletonLine width="w-2/3" height="h-4" />
          <SkeletonLine width="w-1/3" height="h-3" />
        </div>
      </div>
      <div className="space-y-2 pt-2">
        {Array.from({ length: lines }).map((_, i) => (
          <SkeletonLine
            key={i}
            width={i === lines - 1 ? 'w-4/5' : 'w-full'}
            height="h-3.5"
          />
        ))}
      </div>
    </div>
  )
}

export default function Skeleton({
  variant = 'line',
  className = '',
  width,
  height,
  lines,
  size,
  ...props
}) {
  switch (variant) {
    case 'circle':
      return <SkeletonCircle size={size} className={className} {...props} />
    case 'card':
      return <SkeletonCard lines={lines} className={className} {...props} />
    case 'button':
      return (
        <SkeletonButton
          width={width}
          height={height}
          className={className}
          {...props}
        />
      )
    case 'line':
    default:
      return (
        <SkeletonLine
          width={width}
          height={height}
          className={className}
          {...props}
        />
      )
  }
}

Skeleton.Line = SkeletonLine
Skeleton.Circle = SkeletonCircle
Skeleton.Button = SkeletonButton
Skeleton.Card = SkeletonCard
