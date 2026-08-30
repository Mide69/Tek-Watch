'use client'

import { useState, useEffect } from 'react'
import { isDemoMode, isDemoSession } from '@/lib/demoMode'

/**
 * useAuth — returns the current authenticated user.
 *
 * Demo mode (no real Cognito): returns TT-DEMO immediately, no redirect.
 * Production mode (real Cognito pool): validates session and redirects to
 * /login when unauthenticated.
 *
 * A visitor-opted demo session (?demo=1) also skips the redirect, so the
 * landing page's "Launch Live Demo" works against a real Cognito build. They
 * get no token, so the API rejects every call and useData falls back to its
 * mock data — which is exactly the sample dashboard we want to show them.
 */

const IS_REAL_COGNITO = !isDemoMode()

export function useAuth() {
  const [customerId, setCustomerId] = useState<string | null>('TT-DEMO')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!IS_REAL_COGNITO) return   // Demo / dev mode — skip Cognito entirely
    if (isDemoSession()) return    // Browsing the demo — show samples, do not redirect

    let cancelled = false
    setLoading(true)

    async function check() {
      try {
        const { configureAmplify, getAuthUser } = await import('@/lib/auth')
        const { default: apiClient } = await import('@/lib/api')
        const { useRouter } = await import('next/navigation')
        configureAmplify()
        const user = await getAuthUser()
        if (cancelled) return
        if (!user) {
          window.location.replace('/login')
          return
        }
        apiClient.setToken(user.idToken)
        setCustomerId(user.customerId)
      } catch {
        if (!cancelled) window.location.replace('/login')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    check()
    return () => { cancelled = true }
  }, [])

  return { customerId, loading }
}
