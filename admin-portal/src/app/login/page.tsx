'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, ArrowRight } from 'lucide-react'
import {
  configureAmplify,
  adminSignIn,
  adminRespond,
  getAdminToken,
  type AdminAuthStep,
} from '@/lib/auth'
import { isDemoMode } from '@/lib/demoMode'
import adminApi from '@/lib/api'

configureAmplify()
const DEMO = isDemoMode()

export default function AdminLoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  // null = still on the email/password form; anything else is a pending challenge.
  const [step, setStep] = useState<AdminAuthStep | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resetToStart = () => {
    setStep(null)
    setMfaCode('')
    setNewPassword('')
    setConfirmPassword('')
    setError('')
  }

  // A single place to land the session, since three different branches finish.
  const complete = () => {
    const token = getAdminToken()
    if (token) adminApi.setToken(token)
    router.push('/customers')
  }

  // Answering one challenge often reveals the next (new password -> TOTP setup
  // -> done), so advance until Cognito says DONE rather than assuming one hop.
  const advance = (next: AdminAuthStep) => {
    if (next.kind === 'DONE') complete()
    else {
      setStep(next)
      setMfaCode('')
      setNewPassword('')
      setConfirmPassword('')
    }
  }

  useEffect(() => {
    const token = getAdminToken()
    if (token) {
      adminApi.setToken(token)
      router.replace('/customers')
    }
  }, [router])

  const enterDemo = async () => {
    setError('')
    setLoading(true)
    try {
      await adminSignIn('demo@tektribe.io', 'demo')
      complete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not enter demo')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (step === null) {
        advance(await adminSignIn(email, password))
      } else if (step.kind === 'NEW_PASSWORD_REQUIRED') {
        // Cognito enforces the pool's policy server-side; this only catches the
        // mismatch early so the user is not bounced by a round trip.
        if (newPassword !== confirmPassword) {
          throw new Error('Passwords do not match')
        }
        advance(await adminRespond(newPassword))
      } else {
        // Both TOTP_SETUP and TOTP_CODE are answered with a 6-digit code.
        if (!mfaCode || mfaCode.length !== 6) {
          throw new Error('Enter the 6-digit code from your authenticator app')
        }
        advance(await adminRespond(mfaCode))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md animate-fade-up">
        {/* Brand mark */}
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl aurora-grad shadow-2xl shadow-violet-900/50">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">Tek Watch</span>
          </h1>
          <p className="mt-1 text-sm text-muted-ink">Platform Admin · command center</p>
        </div>

        <div className="glass-card p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {step === null ? (
              <>
                <div>
                  <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-muted-ink">
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-glass"
                    placeholder="admin@tektribe.io"
                  />
                </div>
                <div>
                  <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-muted-ink">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-glass"
                    placeholder="••••••••••••"
                  />
                </div>
              </>
            ) : step.kind === 'NEW_PASSWORD_REQUIRED' ? (
              <div className="space-y-4">
                <p className="text-center text-sm text-muted-ink">
                  Choose a new password to replace the temporary one.
                </p>
                <div>
                  <label
                    htmlFor="newPassword"
                    className="mb-1.5 block text-sm font-medium text-muted-ink"
                  >
                    New password
                  </label>
                  <input
                    id="newPassword"
                    type="password"
                    required
                    minLength={16}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="input-glass"
                    placeholder="••••••••••••••••"
                    autoFocus
                  />
                  <p className="mt-1.5 text-xs text-faint-ink">
                    At least 16 characters, with upper and lower case, a number and a symbol.
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="confirmPassword"
                    className="mb-1.5 block text-sm font-medium text-muted-ink"
                  >
                    Confirm new password
                  </label>
                  <input
                    id="confirmPassword"
                    type="password"
                    required
                    minLength={16}
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="input-glass"
                    placeholder="••••••••••••••••"
                  />
                </div>
              </div>
            ) : (
              <div>
                {step.kind === 'TOTP_SETUP' ? (
                  <div className="mb-5 space-y-3">
                    <p className="text-center text-sm text-muted-ink">
                      Set up multi-factor authentication. Add this secret to your authenticator
                      app, then enter the code it shows.
                    </p>
                    <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
                      <p className="mb-1 text-xs uppercase tracking-widest text-faint-ink">
                        Setup key
                      </p>
                      <code className="block break-all font-mono text-sm text-violet-200">
                        {step.secret}
                      </code>
                    </div>
                    <a
                      href={step.setupUri}
                      className="block text-center text-xs text-violet-300 hover:text-violet-200"
                    >
                      Or open directly in your authenticator app →
                    </a>
                  </div>
                ) : (
                  <p className="mb-4 text-center text-sm text-muted-ink">
                    Enter the 6-digit code from your authenticator app
                  </p>
                )}
                <label htmlFor="mfaCode" className="mb-1.5 block text-sm font-medium text-muted-ink">
                  MFA code
                </label>
                <input
                  id="mfaCode"
                  type="text"
                  required
                  maxLength={6}
                  pattern="[0-9]{6}"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                  className="input-glass text-center font-mono text-2xl tracking-[0.5em]"
                  placeholder="000000"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={resetToStart}
                  className="mt-3 text-sm text-violet-300 hover:text-violet-200"
                >
                  ← Back to login
                </button>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading
                ? 'Authenticating…'
                : step === null
                  ? 'Continue'
                  : step.kind === 'NEW_PASSWORD_REQUIRED'
                    ? 'Set password'
                    : step.kind === 'TOTP_SETUP'
                      ? 'Verify and enable MFA'
                      : 'Verify code'}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          {DEMO && (
            <div className="mt-5">
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-white/10" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-transparent px-3 text-xs uppercase tracking-widest text-faint-ink">demo</span>
                </div>
              </div>
              <button type="button" onClick={enterDemo} disabled={loading} className="btn-ghost w-full">
                Enter demo — no credentials needed
              </button>
              <p className="mt-2 text-center text-xs text-faint-ink">
                Sample data only · no AWS backend · or sign in above with any email/password
              </p>
            </div>
          )}
        </div>

        <div className="mt-6 text-center text-xs text-faint-ink">
          <p>Admin access only · all actions are logged</p>
        </div>
      </div>
    </div>
  )
}
