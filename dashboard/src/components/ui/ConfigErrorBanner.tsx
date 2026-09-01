'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { isMisconfigured } from '@/lib/demoMode'

/**
 * Says out loud that this deployment has no authentication configured.
 *
 * A build shipped without its Cognito secrets used to be indistinguishable
 * from a working one: it fell back to demo behaviour, served sample data, and
 * accepted any credentials at the login form. Nobody looking at it could tell.
 * If it happens again it says so, on every page, in red.
 */
export function ConfigErrorBanner() {
  const [broken, setBroken] = useState(false)

  // In an effect because the check reads window.location, and this is a static
  // export: doing it during render would disagree with the server's markup.
  useEffect(() => { setBroken(isMisconfigured()) }, [])

  if (!broken) return null

  return (
    <div
      role="alert"
      className="mb-4 flex items-start gap-2.5 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
      <div className="text-sm">
        <p className="font-semibold text-red-600 dark:text-red-400">
          This deployment is missing its sign-in configuration
        </p>
        <p className="mt-0.5 text-red-700/80 dark:text-red-200/70">
          Nothing here is connected to an account, and anything shown below is
          sample data. Please contact support@tekwatch.io.
        </p>
      </div>
    </div>
  )
}
