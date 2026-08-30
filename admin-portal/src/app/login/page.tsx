'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Shield, ArrowRight, ArrowLeft, Check } from 'lucide-react'
import {
  configureAmplify,
  adminSignIn,
  adminRespond,
  adminForgotPassword,
  adminConfirmForgotPassword,
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
  const [resetCode, setResetCode] = useState('')
  const [qrDataUrl, setQrDataUrl] = useState('')
  // null = still on the email/password form; anything else is a pending challenge.
  const [step, setStep] = useState<AdminAuthStep | null>(null)
  // Forgot-password is a separate track from the sign-in state machine.
  const [view, setView] = useState<'signin' | 'forgot' | 'forgot-confirm' | 'forgot-done'>('signin')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resetToStart = () => {
    setStep(null)
    setView('signin')
    setMfaCode('')
    setNewPassword('')
    setConfirmPassword('')
    setResetCode('')
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
    else if (next.kind === 'RESET_REQUIRED') {
      // Cognito already emailed the code when the reset was triggered, so go
      // straight to code entry rather than making them request another.
      setStep(null)
      setView('forgot-confirm')
      setError('')
    } else {
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

  // Render the otpauth:// URI as a scannable QR. Generated in the browser on
  // purpose — the setup URI contains the TOTP shared secret, so handing it to an
  // external QR service would hand away the second factor. Imported dynamically
  // so the encoder is only fetched when someone actually enrols, rather than
  // riding along in the main bundle of a static export.
  useEffect(() => {
    if (step?.kind !== 'TOTP_SETUP') {
      setQrDataUrl('')
      return
    }
    let cancelled = false
    import('qrcode')
      .then((QRCode) =>
        QRCode.toDataURL(step.setupUri, {
          margin: 2,
          width: 220,
          errorCorrectionLevel: 'M',
          // Fixed dark-on-white regardless of theme; inverted codes are
          // unreliable to scan, which is why it sits on a white plate below.
          color: { dark: '#0B1020', light: '#FFFFFF' },
        })
      )
      .then((url) => {
        if (!cancelled) setQrDataUrl(url)
      })
      .catch(() => {
        // Fall back to manual entry of the setup key, which is always shown.
        if (!cancelled) setQrDataUrl('')
      })
    return () => {
      cancelled = true
    }
  }, [step])

  const enterDemo = async () => {
    setError('')
    setLoading(true)
    try {
      await adminSignIn('demo@tekwatch.io', 'demo')
      complete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not enter demo')
    } finally {
      setLoading(false)
    }
  }

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await adminForgotPassword(email)
      setView('forgot-confirm')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the reset')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (newPassword !== confirmPassword) throw new Error('Passwords do not match')
      await adminConfirmForgotPassword(email, resetCode, newPassword)
      setView('forgot-done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reset the password')
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
      // An account left in RESET_REQUIRED by admin-reset-user-password surfaces
      // as a thrown exception, not as a sign-in step, so the RESET_REQUIRED step
      // handling in advance() never sees it. Send them to code entry instead of
      // showing a dead end — Cognito already emailed the code.
      if ((err as { name?: string })?.name === 'PasswordResetRequiredException') {
        setStep(null)
        setView('forgot-confirm')
        setError('Your password was reset. Enter the code we emailed you and choose a new password.')
      } else {
        setError(err instanceof Error ? err.message : 'Authentication failed')
      }
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
          {view === 'forgot' && (
            <form onSubmit={handleForgot} className="space-y-4">
              <button
                type="button"
                onClick={resetToStart}
                className="flex items-center gap-1.5 text-sm text-violet-300 hover:text-violet-200"
              >
                <ArrowLeft className="h-4 w-4" /> Back to sign in
              </button>
              <div>
                <h2 className="text-lg font-semibold">Reset your password</h2>
                <p className="mt-1 text-sm text-muted-ink">
                  We will email you a 6-digit code to set a new password.
                </p>
              </div>
              <div>
                <label htmlFor="resetEmail" className="mb-1.5 block text-sm font-medium text-muted-ink">
                  Email address
                </label>
                <input
                  id="resetEmail"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-glass"
                  placeholder="admin@tekwatch.io"
                  autoFocus
                />
              </div>
              {error && (
                <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                  {error}
                </div>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Sending…' : 'Send code'}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </form>
          )}

          {view === 'forgot-confirm' && (
            <form onSubmit={handleForgotConfirm} className="space-y-4">
              <button
                type="button"
                onClick={() => { setView('forgot'); setError('') }}
                className="flex items-center gap-1.5 text-sm text-violet-300 hover:text-violet-200"
              >
                <ArrowLeft className="h-4 w-4" /> Use a different email
              </button>
              <div>
                <h2 className="text-lg font-semibold">Enter your code</h2>
                <p className="mt-1 text-sm text-muted-ink">
                  If an account exists for {email}, a 6-digit code is on its way.
                </p>
              </div>
              <div>
                <label htmlFor="resetCode" className="mb-1.5 block text-sm font-medium text-muted-ink">
                  Reset code
                </label>
                <input
                  id="resetCode"
                  type="text"
                  required
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={resetCode}
                  onChange={(e) => setResetCode(e.target.value.replace(/\D/g, ''))}
                  className="input-glass text-center font-mono text-2xl tracking-[0.5em]"
                  placeholder="000000"
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor="resetNew" className="mb-1.5 block text-sm font-medium text-muted-ink">
                  New password
                </label>
                <input
                  id="resetNew"
                  type="password"
                  required
                  minLength={7}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-glass"
                  placeholder="•••••••"
                />
                <p className="mt-1.5 text-xs text-faint-ink">
                  At least 7 characters, with upper and lower case, a number and a symbol.
                </p>
              </div>
              <div>
                <label htmlFor="resetConfirm" className="mb-1.5 block text-sm font-medium text-muted-ink">
                  Confirm new password
                </label>
                <input
                  id="resetConfirm"
                  type="password"
                  required
                  minLength={7}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-glass"
                  placeholder="•••••••"
                />
              </div>
              {error && (
                <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                  {error}
                </div>
              )}
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Resetting…' : 'Set new password'}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </form>
          )}

          {view === 'forgot-done' && (
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full border border-emerald-400/25 bg-emerald-500/15">
                <Check className="h-7 w-7 text-emerald-300" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Password updated</h2>
                <p className="mt-1 text-sm text-muted-ink">
                  Sign in with your new password. You will be asked for your authenticator code.
                </p>
              </div>
              <button type="button" onClick={resetToStart} className="btn-primary w-full">
                Back to sign in
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            className={view === 'signin' ? 'space-y-4' : 'hidden'}
            aria-hidden={view !== 'signin'}
          >
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
                    placeholder="admin@tekwatch.io"
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
                    placeholder="•••••••"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => { setView('forgot'); setError('') }}
                  className="text-sm text-violet-300 hover:text-violet-200"
                >
                  Forgot your password?
                </button>
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
                    At least 7 characters, with upper and lower case, a number and a symbol.
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
                  <div className="mb-5 space-y-4">
                    <p className="text-center text-sm text-muted-ink">
                      Scan this with your authenticator app — Okta Verify, Google Authenticator,
                      Authy, 1Password — then enter the code it shows.
                    </p>

                    {qrDataUrl ? (
                      <div className="flex justify-center">
                        {/* White plate: QR codes scan far more reliably dark-on-light. */}
                        <div className="rounded-xl bg-white p-3 shadow-lg">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={qrDataUrl}
                            alt="QR code for setting up multi-factor authentication"
                            width={220}
                            height={220}
                            className="block h-[220px] w-[220px]"
                          />
                        </div>
                      </div>
                    ) : (
                      <p className="text-center text-xs text-faint-ink">
                        Preparing QR code — use the setup key below if it does not appear.
                      </p>
                    )}

                    <a
                      href={step.setupUri}
                      className="block text-center text-xs text-violet-300 hover:text-violet-200"
                    >
                      Open directly in your authenticator app →
                    </a>

                    <details className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
                      <summary className="cursor-pointer text-xs uppercase tracking-widest text-faint-ink">
                        Can&apos;t scan? Enter the key manually
                      </summary>
                      <code className="mt-2 block break-all font-mono text-sm text-violet-200">
                        {step.secret}
                      </code>
                    </details>
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

          {DEMO && view === 'signin' && (
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
