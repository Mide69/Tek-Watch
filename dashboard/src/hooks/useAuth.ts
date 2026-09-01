'use client'

import { useState, useEffect } from 'react'
import { isDemoBuild, isDemoSession, isMisconfigured } from '@/lib/demoMode'

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

export function useAuth() {
  // Starts null for everyone. Only a demo build resolves to TT-DEMO, and it
  // does so in the effect, once the browser can be asked. Seeding it with the
  // demo id meant a customer who had just signed in was greeted as the demo
  // user, and stayed that way for good if the lookup came back without a
  // username. Deciding it at module load was the same mistake one level up:
  // whether this is a demo now depends on whether someone is signed in, which
  // is not knowable at import time.
  const [customerId, setCustomerId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [configError, setConfigError] = useState(false)

  useEffect(() => {
    // A deployed build with no Cognito configuration. Not a demo — a broken
    // deployment, and it must not quietly behave like a signed-in dashboard.
    if (isMisconfigured()) { setConfigError(true); return }

    if (isDemoBuild()) { setCustomerId('TT-DEMO'); return }

    // A visitor exploring the sample estate. isDemoSession is false the moment
    // a session exists, so a signed-in customer never lands here.
    if (isDemoSession()) { setCustomerId('TT-DEMO'); return }

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
        // Empty is not a customer id. Left as-is it is falsy, and every
        // `customerId || 'TT-DEMO'` downstream quietly resolved to the demo.
        setCustomerId(user.customerId || null)
      } catch {
        if (!cancelled) window.location.replace('/login')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    check()
    return () => { cancelled = true }
  }, [])

  return { customerId, loading, configError }
}
