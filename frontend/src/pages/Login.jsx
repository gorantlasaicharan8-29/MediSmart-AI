import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { Button, Input, ClinicalIcon } from '../components/ui'
import AuthBackground from '../components/auth/AuthBackground'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Notification from previous redirects (e.g. successful registration)
  const successMessage = location.state?.message

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage(null)

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!email.trim() || !emailRegex.test(email.trim())) {
      setErrorMessage('Please enter a valid email address (e.g. name@example.com).')
      return
    }
    if (!password) {
      setErrorMessage('Please enter your password.')
      return
    }

    setIsSubmitting(true)

    try {
      const loggedInUser = await login({ email: email.trim(), password })
      // Navigate to intended page or role workspace
      const defaultTarget = loggedInUser?.role === 'doctor' ? '/doctor' : '/'
      const destination = location.state?.from?.pathname || defaultTarget
      navigate(destination, { replace: true })
    } catch (err) {
      if (err.status === 401) {
        setErrorMessage(
          'Invalid email or password. Please check your credentials and try again.'
        )
      } else if (err.status === 403) {
        setErrorMessage(
          'This account is inactive or suspended. Please contact your hospital administrator.'
        )
      } else {
        setErrorMessage(
          err.message || 'An unexpected error occurred during sign in. Please try again.'
        )
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthBackground badgeText="Secure Clinical Gateway">
      <div className="w-full max-w-md bg-white/95 backdrop-blur-md rounded-2xl sm:rounded-3xl border border-white/60 p-6 sm:p-8 shadow-2xl space-y-6">
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
              Sign In to MediSmart AI
            </h1>
            <p className="text-xs text-brand-muted">
              Enter your credentials to access your clinical dashboard
            </p>
          </div>
        </div>

        {/* Success Banner */}
        {successMessage && (
          <div
            role="status"
            className="p-3.5 rounded-xl bg-clinical-success-bg border border-clinical-success-border text-xs text-clinical-success flex items-start gap-2.5"
          >
            <ClinicalIcon
              name="check-circle"
              size={16}
              className="shrink-0 mt-0.5 text-clinical-success"
              ariaHidden="true"
            />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Banner */}
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
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

          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-brand-text">
                Password
              </span>
              <span
                tabIndex={0}
                role="button"
                className="text-xs text-brand-accent hover:text-brand-deep hover:underline cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-accent rounded"
                onClick={() =>
                  alert(
                    'For demonstration accounts, use your registered password or contact your local administrator.'
                  )
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    alert(
                      'For demonstration accounts, use your registered password or contact your local administrator.'
                    )
                  }
                }}
              >
                Forgot password?
              </span>
            </div>

            <Input
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
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
          </div>

          <div className="p-3 rounded-xl bg-brand-ground border border-brand-border/70 text-[11px] text-brand-muted flex items-start gap-2">
            <ClinicalIcon
              name="info"
              size={14}
              className="text-brand-accent shrink-0 mt-0.5"
              ariaHidden="true"
            />
            <span>
              Role-based permissions (Patient, Doctor, Admin) are verified securely by backend RBAC via HttpOnly cookies.
            </span>
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isSubmitting}
            className="w-full text-sm font-semibold justify-center h-11"
          >
            Sign In
          </Button>
        </form>

        {/* Footer Link */}
        <div className="text-center pt-1 text-xs text-brand-muted">
          Don't have an account yet?{' '}
          <Link
            to="/register"
            className="text-brand-accent font-bold hover:text-brand-deep hover:underline"
          >
            Create an Account
          </Link>
        </div>
      </div>
    </AuthBackground>
  )
}
