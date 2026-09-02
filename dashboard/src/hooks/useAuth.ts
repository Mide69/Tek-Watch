'use client'

import { useState, useEffect } from 'react'
import { isDemoBuild, isDemoSession, isMisconfigured } from '@/lib/demoMode'

/**
 * useAuth — who is looking at this dashboard.
 *
 * Precedence, highest first:
 *
 *   1. Misconfigured deployment. No Cognito to authenticate against, so there
 *      is nothing to do but let ConfigErrorBanner say so.
 *   2. A demo tab, or a demo build. TT-DEMO, no redirect, sample estate — and
 *      deliberately so even for someone signed in, because you should be able
 *      to look at the demo without signing out of your own account.
 *   3. Otherwise: validate with Cognito, redirect to /login if there is none.
 *
 * What keeps 2 from leaking into 3 is that the demo now lives in
 * sessionStorage, so it belongs to the tab it was opened in. An account tab
 * never carries the flag and so can never show fixtures. Previously it lived
 * in localStorage, shared across every tab and surviving a browser restart,
 * which is how a customer ended up signed in and labelled TT-DEMO.
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

    if (isDemoBuild() || isDemoSession()) {
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
