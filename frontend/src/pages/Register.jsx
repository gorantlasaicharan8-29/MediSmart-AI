import React, { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { Button, Input, Select, ClinicalIcon } from '../components/ui'
import AuthBackground from '../components/auth/AuthBackground'

export default function Register() {
  const [role, setRole] = useState('patient')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { register } = useAuth()
  const navigate = useNavigate()

  // Calculate accessible password strength metrics
  const passwordStrength = useMemo(() => {
    if (!password) return { score: 0, label: 'None', color: 'bg-stone-200' }
    let score = 0
    if (password.length >= 8) score += 1
    if (password.length >= 12) score += 1
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1
    if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score += 1

    if (score <= 1) {
      return { score: 1, label: 'Weak', color: 'bg-clinical-danger', text: 'text-clinical-danger' }
    }
    if (score === 2) {
      return { score: 2, label: 'Fair', color: 'bg-amber-400', text: 'text-amber-700' }
    }
    if (score === 3) {
      return { score: 3, label: 'Good', color: 'bg-teal-500', text: 'text-teal-700' }
    }
    return { score: 4, label: 'Strong', color: 'bg-clinical-success', text: 'text-clinical-success' }
  }, [password])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)

    if (fullName.trim().length < 2) {
      setErrorMessage('Full name must be at least 2 characters.')
      return
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!email.trim() || !emailRegex.test(email.trim())) {
      setErrorMessage('Please provide a valid email address (e.g. name@example.com).')
      return
    }

    if (password.length < 8) {
      setErrorMessage('Password must be at least 8 characters in length.')
      return
    }

    setIsSubmitting(true)

    try {
      await register({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        phone: phone.trim() || null,
        role,
      })

      // Redirect to login with success notice
      navigate('/login', {
        state: {
          message: 'Account created successfully! Please sign in with your email and password.',
        },
      })
    } catch (err) {
      if (err.status === 409) {
        setErrorMessage(
          'An account with this email address already exists. Please sign in or use another email.'
        )
      } else if (err.status === 403) {
        setErrorMessage(
          'Administrative roles cannot be self-assigned. Contact your system administrator.'
        )
      } else {
        setErrorMessage(
          err.message || 'An error occurred during registration. Please try again.'
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthBackground badgeText="Patient & Provider Registration">
      <div className="w-full max-w-lg bg-white/95 backdrop-blur-md rounded-2xl sm:rounded-3xl border border-white/60 p-6 sm:p-8 shadow-2xl space-y-6 my-2">
        {/* Official MediSmart AI Healthcare Branding */}
        <div className="text-center space-y-3">
          <Link
            to="/"
            className="inline-block group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent rounded-2xl"
            aria-label="MediSmart AI Home"
          >
            <div className="inline-flex items-center justify-center p-2.5 rounded-2xl bg-gradient-to-b from-brand-ground/90 to-brand-mint/20 border border-brand-border/70 shadow-clinical-xs backdrop-blur-sm group-hover:border-teal-300 transition-colors">
              <img
                src="/images/medismart-logo.png"
                alt="MediSmart AI Healthcare Logo"
                className="h-20 sm:h-24 w-auto object-contain mx-auto group-hover:scale-105 transition-transform"
              />
            </div>
          </Link>
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-brand-text tracking-tight">
              Create your MediSmart AI Account
            </h1>
            <p className="text-xs text-brand-muted">
              Join the digital healthcare and queue coordination network
            </p>
          </div>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div
            role="alert"
            className="p-3.5 rounded-xl bg-clinical-danger-bg border border-clinical-danger-border text-xs text-clinical-danger flex items-start gap-2.5"
          >
            <ClinicalIcon
              name="alert-circle"
              size={16}
              className="shrink-0 mt-0.5 text-clinical-danger"
              ariaHidden="true"
            />
            <span>{errorMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4.5" noValidate>
          {/* Account Role */}
          <Select
            label="Account Classification"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            disabled={isSubmitting}
            leftIcon={
              <ClinicalIcon
                name={role === 'doctor' ? 'stethoscope' : 'user'}
                size={16}
                ariaHidden="true"
              />
            }
          >
            <option value="patient">Patient &mdash; Book Appointments &amp; Track Live Queue</option>
            <option value="doctor">Doctor &mdash; Consultations &amp; Queue Management</option>
          </Select>

          {/* Admin role callout */}
          <div className="p-3 rounded-xl bg-brand-ground border border-brand-border/70 text-[11px] text-brand-muted flex items-start gap-2">
            <ClinicalIcon
              name="info"
              size={14}
              className="text-brand-accent shrink-0 mt-0.5"
              ariaHidden="true"
            />
            <span>
              <strong>Administrative Accounts:</strong> Hospital Admin and System Admin credentials are provisioned directly by authorized institutional staff and cannot be self-registered.
            </span>
          </div>

          {/* Full Name */}
          <Input
            label="Full Legal Name"
            type="text"
            required
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder={role === 'doctor' ? 'e.g. Dr. Sarah Mitchell' : 'e.g. John Doe'}
            disabled={isSubmitting}
            leftIcon={
              <ClinicalIcon
                name="user"
                size={16}
                className="text-brand-muted"
                ariaHidden="true"
              />
            }
          />

          {/* Email */}
          <Input
            label="Email Address"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
            disabled={isSubmitting}
            leftIcon={
              <ClinicalIcon
                name="user"
                size={16}
                className="text-brand-muted"
                ariaHidden="true"
              />
            }
          />

          {/* Phone */}
          <Input
            label="Contact Phone Number"
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 (555) 000-0000"
            helperText="Optional &mdash; Used for SMS appointment reminders and ticket notifications"
            disabled={isSubmitting}
            leftIcon={
              <ClinicalIcon
                name="heart-pulse"
                size={16}
                className="text-brand-muted"
                ariaHidden="true"
              />
            }
          />

          {/* Password */}
          <div>
            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              disabled={isSubmitting}
              leftIcon={
                <ClinicalIcon
                  name="shield-check"
                  size={16}
                  className="text-brand-muted"
                  ariaHidden="true"
                />
              }
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-brand-muted hover:text-brand-text p-1 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent cursor-pointer"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <ClinicalIcon
                    name={showPassword ? 'eye-off' : 'eye'}
                    size={16}
                    ariaHidden="true"
                  />
                </button>
              }
            />

            {/* Password Strength Indicator */}
            {password.length > 0 && (
              <div className="mt-2 space-y-1.5" aria-live="polite">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-brand-muted">
                    Strength:{' '}
                    <strong className={passwordStrength.text}>
                      {passwordStrength.label}
                    </strong>
                  </span>
                  <span className="text-[10px] text-brand-muted font-mono">
                    {password.length >= 8 ? '&ge; 8 characters &check;' : 'Need 8+ chars'}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5 h-1.5">
                  {[1, 2, 3, 4].map((step) => (
                    <div
                      key={step}
                      className={`h-full rounded-full transition-all duration-200 ${
                        passwordStrength.score >= step
                          ? passwordStrength.color
                          : 'bg-stone-200'
                      }`}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Submit */}
          <div className="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSubmitting}
              className="w-full text-sm font-semibold justify-center h-11"
            >
              Complete Registration
            </Button>
          </div>
        </form>

        {/* Footer */}
        <div className="text-center pt-1 text-xs text-brand-muted">
          Already have an account?{' '}
          <Link
            to="/login"
            className="text-brand-accent font-bold hover:text-brand-deep hover:underline"
          >
            Sign In
          </Link>
        </div>
      </div>
    </AuthBackground>
  )
}
