'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { mutate as revalidateAll } from 'swr'
import { isDemoBuild, isDemoSession, isMisconfigured } from '@/lib/demoMode'
import { resetDataSource } from '@/lib/dataSource'

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
 *
 * This resolves once per browser session, not once per page.
 *
 * Every dashboard page used to call this hook directly at its own top level,
 * which meant a fresh instance — fresh state, fresh effect — mounted on
 * every single navigation, because each route is its own React component
 * that Next.js tears down and rebuilds on the way to the next one. Clicking
 * through five pages in the time Cognito's own session lookup takes to
 * resolve raced five separate checks, most of which got cancelled by the
 * very next navigation before their own correction (see revalidateAll below)
 * ever ran — leaving whatever the interrupted page had already fetched, sample
 * data or empty zeros, on screen indefinitely. Nothing ever asked again,
 * because nothing was still mounted to ask.
 *
 * AuthProvider now does this check exactly once, mounted in the shared
 * dashboard layout that survives every route change within it. Every page
 * still calls the plain useAuth() hook below unchanged — it just reads a
 * result that was settled once, cleanly, instead of racing to re-settle it
 * on every click.
 */

interface AuthState {
  customerId: string | null
  loading: boolean
}

const AuthContext = createContext<AuthState>({ customerId: null, loading: false })

export function AuthProvider({ children }: { children: ReactNode }) {
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

        // Every data hook mounts and starts fetching in the same render pass
        // as this effect — in parallel with the Cognito session lookup
        // above, not after it. A hook whose first fetch landed before this
        // line ran found no token yet, so apiFetch's own "not signed in"
        // fallback answered it: sample data, or an empty-but-real-shaped
        // response. SWR treated that as resolved and had no reason to ask
        // again on its own.
        //
        // The sample-data flag those fallbacks set is also global, not
        // page-scoped, and nothing used to clear a path's entry when the
        // page that set it was left before it ever got a chance to correct
        // itself — so a single early race, on a page visited once and never
        // revisited, kept the "no data yet" banner showing on every other
        // page for the rest of the session, even ones already displaying
        // real, correct data underneath it. Clearing the slate before
        // asking everything currently mounted to refetch means what's shown
        // reflects this attempt, not whatever an earlier, abandoned one left
        // behind.
        resetDataSource()
        revalidateAll(() => true)
      } catch {
        if (!cancelled) window.location.replace('/login')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    check()
    return () => { cancelled = true }
  }, [])

  return (
    <AuthContext.Provider value={{ customerId, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  return useContext(AuthContext)
}
