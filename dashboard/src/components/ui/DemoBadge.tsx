'use client'

import Link from 'next/link'
import { Sparkles } from 'lucide-react'
import { useFixtureView } from '@/hooks/useFixtureView'

/**
 * Tells a visitor they are looking at sample data, and gives them a way in.
 *
 * The demo deliberately renders the real dashboard rather than a cut-down
 * preview, so someone evaluating the product sees exactly what they would get
 * after signing up. That realism is the point — but it means nothing on screen
 * would otherwise distinguish sample figures from their own account.
 *
 * Resolved in an effect rather than during render: isDemoSession() reads
 * localStorage, which does not exist server-side, and this is a static export.
 * Reading it during render would produce markup that disagrees with the
 * server's and trigger a hydration mismatch.
 */
export function DemoBadge() {
  const isDemo = useFixtureView()

  if (!isDemo) return null

  return (
    <div className="flex items-center gap-2">
      {/* Was hidden below the sm breakpoint, which left a phone showing the
          "Start free trial" button with nothing to say the figures beside it
          were samples. The label is the whole point of the badge, so it is the
          part that stays; only the word "Demo" is dropped when space is tight. */}
      <span className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-xs font-medium text-cyan-600 dark:text-cyan-300 whitespace-nowrap">
        <Sparkles className="h-3 w-3 flex-shrink-0" />
        <span className="hidden sm:inline">Demo &middot;&nbsp;</span>sample data
      </span>
      <Link
        href="/signup"
        className="rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90"
      >
        Start free trial
      </Link>
    </div>
  )
}
