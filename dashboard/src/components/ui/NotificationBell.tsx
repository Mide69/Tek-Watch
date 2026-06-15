'use client'

import Link from 'next/link'
import { Bell } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAlerts } from '@/hooks/useData'

export function NotificationBell() {
  const { data } = useAlerts()
  const alerts = data?.alerts ?? []
  const activeCount = alerts.filter((a: { status: string }) => a.status === 'active').length

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
