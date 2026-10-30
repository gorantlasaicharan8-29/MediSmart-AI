import React from 'react'
import { Link } from 'react-router-dom'
import { Button, ClinicalIcon } from '../components/ui'

export default function NotFound() {
  return (
    <div className="max-w-md mx-auto px-4 py-20 text-center space-y-5">
      <div className="w-16 h-16 rounded-2xl bg-brand-ground border border-brand-border text-brand-primary flex items-center justify-center mx-auto shadow-clinical-xs">
        <ClinicalIcon name="alert-circle" size={32} ariaHidden="true" />
      </div>
      <div className="space-y-1.5">
        <div className="text-4xl font-black text-brand-primary tracking-tight">404</div>
        <h1 className="text-xl font-bold text-brand-text">Page Not Found</h1>
        <p className="text-xs sm:text-sm text-brand-muted max-w-sm mx-auto leading-relaxed">
          The clinic, doctor, or healthcare resource you requested does not exist or has been moved.
        </p>
      </div>
      <div className="pt-2 flex justify-center">
        <Button
          variant="primary"
          size="md"
          as={Link}
          to="/"
          className="text-xs font-bold gap-1.5"
        >
          <ClinicalIcon name="arrow-right" size={14} ariaHidden="true" />
          <span>Return to Homepage</span>
        </Button>
      </div>
    </div>
  )
}
