'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Check } from 'lucide-react'
import { LogoMark } from '@/components/ui/Logo'
import {
  configureAmplify,
  authSignIn,
  authCompleteNewPassword,
  authForgotPassword,
  authConfirmForgotPassword,
} from '@/lib/auth'
import apiClient from '@/lib/api'

configureAmplify()

// 'forgot-sent' collects the emailed code. Cognito sends a numeric CODE, not a
// link, so without this step the reset email had nowhere to be used and anyone
// who forgot their password was permanently locked out.
// 'new-password' is the first sign-in. Signup creates the Cognito user with a
// temporary password, so the very first login is a two-step exchange: Cognito
// issues no tokens until the customer has chosen their own password.
type View = 'login' | 'new-password' | 'forgot' | 'forgot-sent' | 'forgot-done'

export default function LoginPage() {
  const router = useRouter()
  const [view, setView] = useState<View>('login')
  const [customerId, setCustomerId] = useState('')
  const [password, setPassword] = useState('')
  const [resetCode, setResetCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await authSignIn(customerId.toUpperCase(), password)
      if (result.status === 'NEW_PASSWORD_REQUIRED') {
        setNewPassword('')
        setConfirmPassword('')
        setView('new-password')
        return
      }
      enterDashboard(result.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const enterDashboard = (user: { idToken: string; customerId: string }) => {
    apiClient.setToken(user.idToken)
    localStorage.setItem('tek_watch_customer_id', user.customerId)
    router.push('/overview')
  }

  const handleNewPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (newPassword !== confirmPassword) throw new Error('Passwords do not match')
      const user = await authCompleteNewPassword(customerId.toUpperCase(), newPassword)
      enterDashboard(user)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not set your password')
    } finally {
      setLoading(false)
    }
  }

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authForgotPassword(customerId.toUpperCase())
      setView('forgot-sent')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset email')
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
      await authConfirmForgotPassword(customerId.toUpperCase(), resetCode, newPassword)
      setView('forgot-done')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reset the password')
    } finally {
      setLoading(false)
    }
  }

  const inputCls = 'w-full px-3.5 py-2.5 rounded-lg border border-white/[0.1] bg-white/[0.05] text-slate-200 placeholder-slate-600 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition'

  return (
    <div className="min-h-screen bg-[#070c18] flex">
      {/* Left — branding panel */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-center px-12 border-r border-white/[0.06] relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900/30 via-transparent to-violet-900/20 pointer-events-none" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
              <LogoMark className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">Tek Watch</span>
          </div>
          <h2 className="text-3xl font-bold text-white mb-3 leading-snug">
            AWS infrastructure<br />intelligence, unified.
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed mb-10">
            Real-time monitoring across every AWS service and region,
            with AI that spots problems before your customers do.
          </p>
          <ul className="space-y-3">
            {[
              'Real-time metrics across all regions',
              'AI anomaly detection powered by Claude',
              'Threshold alerts & notifications',
              'Cost intelligence & optimisation',
              'Security & compliance visibility',
            ].map(f => (
              <li key={f} className="flex items-center gap-3 text-sm text-slate-300">
                <div className="w-5 h-5 rounded-full bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center flex-shrink-0">
                  <Check className="w-3 h-3 text-indigo-400" />
                </div>
                {f}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Right — form */}
      <div className="flex flex-1 items-center justify-center px-8 py-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
              <LogoMark className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-white">Tek Watch</span>
          </div>

          {view === 'login' && (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Welcome back</h1>
                <p className="text-slate-400 mt-1.5 text-sm">Sign in to your Tek Watch account</p>
              </div>

              <form onSubmit={handleLogin} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Customer ID</label>
                  <input type="text" required placeholder="TT-XXXXXXXX" value={customerId}
                    onChange={e => setCustomerId(e.target.value.toUpperCase())}
                    className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
                  <input type="password" required value={password}
                    onChange={e => setPassword(e.target.value)}
                    className={inputCls} />
                </div>

                {error && (
                  <div className="p-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}

                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>

                <div className="flex items-center justify-between text-sm">
                  <button type="button" onClick={() => { setView('forgot'); setError('') }}
                    className="text-indigo-400 hover:text-indigo-300 transition-colors">
                    Forgot password?
                  </button>
                  <Link href="/overview/?demo=1" className="text-slate-500 hover:text-slate-300 transition-colors text-xs">
                    Try demo instead →
                  </Link>
                </div>
                <p className="text-center text-sm text-slate-500">
                  Don&apos;t have an account?{' '}
                  <Link href="/signup" className="text-indigo-400 hover:text-indigo-300 transition-colors">Sign up</Link>
                </p>
              </form>
            </>
          )}

          {view === 'new-password' && (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Choose your password</h1>
                <p className="text-slate-400 mt-1.5 text-sm">
                  Welcome to Tek Watch. Your temporary password worked — pick a
                  permanent one to finish setting up {customerId}.
                </p>
              </div>
              <form onSubmit={handleNewPassword} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">New password</label>
                  <input type="password" required minLength={7} autoComplete="new-password"
                    placeholder="•••••••" value={newPassword} autoFocus
                    onChange={e => setNewPassword(e.target.value)} className={inputCls} />
                  <p className="mt-1.5 text-xs text-slate-500">
                    At least 7 characters, with upper and lower case and a number.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Confirm new password</label>
                  <input type="password" required minLength={7} autoComplete="new-password"
                    placeholder="•••••••" value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)} className={inputCls} />
                </div>
                {error && (
                  <div className="p-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-colors">
                  {loading ? 'Setting password…' : 'Set password and continue'}
                </button>
              </form>
            </>
          )}

          {view === 'forgot' && (
            <>
              <button onClick={() => { setView('login'); setError('') }}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to login
              </button>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Reset password</h1>
                <p className="text-slate-400 mt-1.5 text-sm">Enter your Customer ID and we&apos;ll email you a 6-digit code.</p>
              </div>
              <form onSubmit={handleForgot} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Customer ID</label>
                  <input type="text" required placeholder="TT-XXXXXXXX" value={customerId}
                    onChange={e => setCustomerId(e.target.value.toUpperCase())} className={inputCls} />
                </div>
                {error && (
                  <div className="p-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-colors">
                  {loading ? 'Sending…' : 'Send reset code'}
                </button>
              </form>
            </>
          )}

          {view === 'forgot-sent' && (
            <>
              <button onClick={() => { setView('forgot'); setError('') }}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
                <ArrowLeft className="w-4 h-4" /> Use a different Customer ID
              </button>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Enter your code</h1>
                <p className="text-slate-400 mt-1.5 text-sm">
                  If an account exists for {customerId}, a 6-digit code is on its way.
                </p>
              </div>
              <form onSubmit={handleForgotConfirm} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Reset code</label>
                  <input type="text" required maxLength={6} inputMode="numeric" autoComplete="one-time-code"
                    placeholder="000000" value={resetCode}
                    onChange={e => setResetCode(e.target.value.replace(/\D/g, ''))}
                    className={`${inputCls} text-center font-mono text-2xl tracking-[0.5em]`} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">New password</label>
                  <input type="password" required minLength={7} autoComplete="new-password"
                    placeholder="•••••••" value={newPassword}
                    onChange={e => setNewPassword(e.target.value)} className={inputCls} />
                  <p className="mt-1.5 text-xs text-slate-500">
                    At least 7 characters, with upper and lower case and a number.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Confirm new password</label>
                  <input type="password" required minLength={7} autoComplete="new-password"
                    placeholder="•••••••" value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)} className={inputCls} />
                </div>
                {error && (
                  <div className="p-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-colors">
                  {loading ? 'Resetting…' : 'Set new password'}
                </button>
              </form>
            </>
          )}

          {view === 'forgot-done' && (
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/15 border border-emerald-500/25 rounded-full flex items-center justify-center mx-auto mb-5">
                <Check className="w-7 h-7 text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Password updated</h2>
              <p className="text-slate-400 text-sm mb-6">
                You can now sign in with your new password.
              </p>
              <button onClick={() => { setView('login'); setError('') }}
                className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                Back to login
              </button>
            </div>
          )}

          <p className="mt-10 text-center text-xs text-slate-600">
            Need help signing in?{' '}
            <a href="mailto:support@tekwatch.io" className="text-indigo-500 hover:text-indigo-400">
              support@tekwatch.io
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
