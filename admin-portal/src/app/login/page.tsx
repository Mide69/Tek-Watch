'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Shield } from 'lucide-react'
import { configureAmplify, adminSignIn, adminConfirmMfa, getAdminToken } from '@/lib/auth'
import { isDemoMode } from '@/lib/demoMode'
import adminApi from '@/lib/api'

configureAmplify()
const DEMO = isDemoMode()

export default function AdminLoginPage() {
  const router = useRouter()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [mfaCode, setMfaCode]   = useState('')
  const [showMfa, setShowMfa]   = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  // Redirect if already authenticated
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
      const token = getAdminToken()
      if (token) adminApi.setToken(token)
      router.push('/customers')
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
      if (!showMfa) {
        // Step 1: email + password
        const { mfaRequired } = await adminSignIn(email, password)
        if (mfaRequired) {
          setShowMfa(true)
        } else {
          // No MFA (dev mode or MFA not configured)
          const token = getAdminToken()
          if (token) adminApi.setToken(token)
          router.push('/customers')
        }
      } else {
        // Step 2: TOTP code
        if (!mfaCode || mfaCode.length !== 6) {
          throw new Error('Enter the 6-digit code from your authenticator app')
        }
        await adminConfirmMfa(mfaCode)
        const token = getAdminToken()
        if (token) adminApi.setToken(token)
        router.push('/customers')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-700 to-blue-900 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-2xl mb-4">
              <Shield className="h-8 w-8 text-blue-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Admin Portal</h1>
            <p className="text-sm text-gray-500 mt-1">Tek Watch Platform Management</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!showMfa ? (
              <>
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="admin@tektribe.io"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </>
            ) : (
              <div>
                <div className="text-center mb-4">
                  <p className="text-sm text-gray-600">
                    Enter the 6-digit code from your authenticator app
                  </p>
                </div>
                <label htmlFor="mfaCode" className="block text-sm font-medium text-gray-700 mb-1.5">
                  MFA Code
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
                  onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                  className="w-full px-3.5 py-3 border border-gray-300 rounded-lg text-center text-2xl tracking-[0.5em] font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="000000"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => { setShowMfa(false); setMfaCode(''); setError('') }}
                  className="mt-3 text-sm text-blue-600 hover:text-blue-700"
                >
                  ← Back to login
                </button>
              </div>
            )}

            {error && (
              <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? 'Authenticating…'
                : showMfa
                  ? 'Verify Code'
                  : 'Continue'}
            </button>
          </form>

          {DEMO && (
            <div className="mt-5">
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                <div className="relative flex justify-center text-xs"><span className="bg-white px-2 text-gray-400">demo</span></div>
              </div>
              <button
                type="button"
                onClick={enterDemo}
                disabled={loading}
                className="w-full py-2.5 px-4 border border-blue-600 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-50 disabled:opacity-50 transition-colors"
              >
                Enter demo (no credentials needed)
              </button>
              <p className="mt-2 text-center text-xs text-gray-400">
                Sample data only — no AWS backend. Or sign in above with any email/password.
              </p>
            </div>
          )}

          <div className="mt-6 text-center text-xs text-gray-400 space-y-1">
            <p>Admin access only. All actions are logged.</p>
            <p>
              Need help?{' '}
              <a href="mailto:ops@tektribe.io" className="text-blue-500 hover:underline">
                ops@tektribe.io
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
