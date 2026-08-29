'use client'

import { useCallback, useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Back / forward controls for the app's own navigation.
 *
 * The browser exposes no way to ask "is there anywhere to go back/forward to?"
 * — history.length counts the whole tab including pages from before this app
 * loaded, and there is no forward-entry count at all. So we track position
 * ourselves: `idx` is where we are in this session's stack and `maxIdx` is how
 * far it extends, which makes Forward correctly go dead at the end of the stack
 * rather than staying lit and doing nothing.
 *
 * That state lives at MODULE scope, not in refs, and this is load-bearing: every
 * page under (dashboard) renders its own <DashboardLayout>, so the layout and
 * everything in it REMOUNTS on each navigation. Instance state resets exactly
 * when we need it to persist. Module scope survives client-side navigation and
 * is discarded on a real page load, which is precisely the lifetime the
 * browser's own forward stack has.
 */
let idx = 0
let maxIdx = 0
let lastPath: string | null = null
let pending: 'back' | 'forward' | null = null

export function HistoryNav({ className }: { className?: string }) {
  const router = useRouter()
  const pathname = usePathname()

  const [canBack, setCanBack] = useState(false)
  const [canForward, setCanForward] = useState(false)

  useEffect(() => {
    if (lastPath === null) {
      lastPath = pathname
    } else if (pathname !== lastPath) {
      lastPath = pathname
      if (pending === 'back') {
        idx = Math.max(0, idx - 1)
      } else if (pending === 'forward') {
        idx = Math.min(maxIdx, idx + 1)
      } else {
        // A fresh navigation truncates whatever was ahead of us.
        idx += 1
        maxIdx = idx
      }
      pending = null
    }

    // idx === 0 can still have somewhere to go back to — the visitor may have
    // arrived from the landing page or another site.
    setCanBack(idx > 0 || window.history.length > 1)
    setCanForward(idx < maxIdx)
  }, [pathname])

  const goBack = useCallback(() => {
    pending = 'back'
    router.back()
  }, [router])

  const goForward = useCallback(() => {
    pending = 'forward'
    router.forward()
  }, [router])

  const base = cn(
    'relative w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200',
    'text-muted-foreground border border-transparent',
    'enabled:hover:text-foreground enabled:hover:bg-accent enabled:hover:border-border',
    'disabled:opacity-35 disabled:cursor-not-allowed'
  )

  return (
    <div className={cn('flex items-center gap-0.5', className)}>
      <button type="button" onClick={goBack} disabled={!canBack} aria-label="Go back" title="Back" className={base}>
        <ChevronLeft className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={goForward}
        disabled={!canForward}
        aria-label="Go forward"
        title="Forward"
        className={base}
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  )
}
