'use client'

import { useState, useEffect } from 'react'

/**
 * useAuth — returns the current authenticated user.
 *
 * Demo mode (no real Cognito): returns TT-DEMO immediately, no redirect.
 * Production mode (real Cognito pool): validates session and redirects to
 * /login when unauthenticated.
 */

const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''
const IS_REAL_COGNITO = (
  COGNITO_POOL.length > 0 &&
  !COGNITO_POOL.includes('placeholder') &&
  COGNITO_POOL !== 'undefined'
)

export function useAuth() {
  const [customerId, setCustomerId] = useState<string | null>('TT-DEMO')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!IS_REAL_COGNITO) return   // Demo / dev mode — skip Cognito entirely

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
