'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Radio, ArrowLeft, Check } from 'lucide-react'
import { configureAmplify, authSignIn, authForgotPassword } from '@/lib/auth'
import apiClient from '@/lib/api'

configureAmplify()

type View = 'login' | 'forgot' | 'forgot-sent'

export default function LoginPage() {
  const router = useRouter()
  const [view, setView] = useState<View>('login')
  const [customerId, setCustomerId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await authSignIn(customerId.toUpperCase(), password)
      apiClient.setToken(user.idToken)
      localStorage.setItem('tek_watch_customer_id', user.customerId)
      router.push('/overview')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed. Check your credentials.')
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

  const inputCls = 'w-full px-3.5 py-2.5 rounded-lg border border-white/[0.1] bg-white/[0.05] text-slate-200 placeholder-slate-600 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition'

  return (
    <div className="min-h-screen bg-[#070c18] flex">
      {/* Left — branding panel */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-center px-12 border-r border-white/[0.06] relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-900/30 via-transparent to-violet-900/20 pointer-events-none" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
              <Radio className="w-5 h-5 text-white" />
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
              <Radio className="w-4 h-4 text-white" />
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
                  <input type="text" required placeholder="TT-0001" value={customerId}
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
                  <Link href="/overview" className="text-slate-500 hover:text-slate-300 transition-colors text-xs">
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

          {view === 'forgot' && (
            <>
              <button onClick={() => { setView('login'); setError('') }}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
                <ArrowLeft className="w-4 h-4" /> Back to login
              </button>
              <div className="mb-8">
                <h1 className="text-2xl font-bold text-white">Reset password</h1>
                <p className="text-slate-400 mt-1.5 text-sm">Enter your Customer ID and we&apos;ll send a reset link.</p>
              </div>
              <form onSubmit={handleForgot} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Customer ID</label>
                  <input type="text" required placeholder="TT-0001" value={customerId}
                    onChange={e => setCustomerId(e.target.value.toUpperCase())} className={inputCls} />
                </div>
                {error && (
                  <div className="p-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg">{error}</div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-colors">
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>
            </>
          )}

          {view === 'forgot-sent' && (
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-500/15 border border-emerald-500/25 rounded-full flex items-center justify-center mx-auto mb-5">
                <Check className="w-7 h-7 text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Check your email</h2>
              <p className="text-slate-400 text-sm mb-6">
                If an account exists for {customerId}, a password reset link has been sent.
              </p>
              <button onClick={() => { setView('login'); setError('') }}
                className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors">
                Back to login
              </button>
            </div>
          )}

          <p className="mt-10 text-center text-xs text-slate-600">
            Need help signing in?{' '}
            <a href="mailto:support@tektribe.io" className="text-indigo-500 hover:text-indigo-400">
              support@tektribe.io
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
