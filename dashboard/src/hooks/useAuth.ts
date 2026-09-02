'use client'

import { useState, useEffect } from 'react'
import { hasCognitoConfig, hasSession, isDemoBuild, isDemoSession, isMisconfigured } from '@/lib/demoMode'

/**
 * useAuth — who is looking at this dashboard.
 *
 * Precedence, highest first:
 *
 *   1. Misconfigured deployment. No Cognito to authenticate against, so there
 *      is nothing to do but let ConfigErrorBanner say so.
 *   2. A real session. Always wins. A customer who is signed in is never the
 *      demo user, whatever else local storage happens to hold.
 *   3. A demo build, or a visitor who chose the demo. TT-DEMO, no redirect,
 *      sample estate.
 *   4. Otherwise: validate with Cognito, redirect to /login if there is no
 *      session.
 *
 * Rule 2 was missing, and it is the one the customer noticed: their company
 * name and "TT-DEMO" on the same line in the sidebar.
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

  useEffect(() => {
    // A deployed build with no Cognito configuration. Not a demo — a broken
    // deployment, and it must not quietly behave like a signed-in dashboard.
    // Nothing to authenticate against. ConfigErrorBanner says so on every
    // page; there is no point redirecting to a login that cannot work either.
    if (isMisconfigured()) return

    // Gated on the build having real Cognito, so `npm run dev` without a pool
    // stays a demo rather than redirecting to a login it cannot serve.
    const signedIn = hasCognitoConfig() && hasSession()
    if (!signedIn && (isDemoBuild() || isDemoSession())) {
      setCustomerId('TT-DEMO')
      return
    }


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

  return { customerId, loading }
}
