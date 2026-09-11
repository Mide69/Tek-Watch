'use client'

import Link from 'next/link'
import { Bell } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAlerts } from '@/hooks/useData'
import { useFixtureView } from '@/hooks/useFixtureView'

export function NotificationBell() {
  const { data } = useAlerts()
  // The alerts' first paint depends on whether this tab is a demo, which is
  // only known in the browser. The server always renders no badge; a demo tab
  // rendered "3" on its first pass, and React reported a hydration mismatch on
  // every dashboard page. Counting only once the viewer is resolved makes the
  // first client render match the server's.
  const viewer = useFixtureView()
  const alerts = viewer === null ? [] : data?.alerts ?? []
  const activeCount = alerts.filter(a => a.status === 'active').length

  return (
    <Link
      href="/alerts"
      className="relative flex items-center justify-center w-8 h-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      title={`${activeCount} active alert${activeCount !== 1 ? 's' : ''}`}
      aria-label={`Alerts — ${activeCount} active`}
    >
      <Bell className="w-4 h-4" />
      {activeCount > 0 && (
        <span
          aria-hidden
          className={cn(
            'absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center',
            'rounded-full bg-red-500 text-white font-bold px-0.5',
            activeCount > 9 ? 'text-[8px]' : 'text-[9px]',
          )}
        >
          {activeCount > 99 ? '99+' : activeCount}
        </span>
      )}
    </Link>
  )
}
