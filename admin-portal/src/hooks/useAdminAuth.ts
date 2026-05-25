/**
 * useAdminAuth — checks admin authentication and redirects to /login if not authenticated.
 * Restores the JWT token into the admin API client on page load.
 */
'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { configureAmplify, getAdminToken } from '@/lib/auth'
import adminApi from '@/lib/api'

configureAmplify()

export function useAdminAuth() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    const token = getAdminToken()
    if (!token) {
      router.replace('/login')
      return
    }
    adminApi.setToken(token)
    setAuthenticated(true)
    setLoading(false)
  }, [router])

  return { loading, authenticated }
}
