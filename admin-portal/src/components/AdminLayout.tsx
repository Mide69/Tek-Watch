'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Users,
  Settings,
  Activity,
  LogOut,
  Menu,
  X,
  Shield,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { adminSignOut } from '@/lib/auth'
import adminApi from '@/lib/api'

const navigation = [
  { name: 'Customers', href: '/customers', icon: Users },
  { name: 'Thresholds', href: '/thresholds', icon: Settings },
  { name: 'Operations', href: '/operations', icon: Activity },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()
  const router = useRouter()

  const handleSignOut = async () => {
    await adminSignOut()
    adminApi.clearToken()
    router.push('/login')
  }

  const Sidebar = () => (
    <div className="flex h-full flex-col glass rounded-none border-y-0 border-l-0">
      {/* Brand */}
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl aurora-grad shadow-lg shadow-violet-900/40">
          <Shield className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight text-ink">Tek Watch</p>
          <p className="text-xs text-faint-ink">Admin Portal</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1.5 px-3 py-4">
        <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-faint-ink">
          Platform
        </p>
        {navigation.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(item.href + '/')
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={() => setSidebarOpen(false)}
              className={cn(
                'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all',
                active ? 'text-white' : 'text-muted-ink hover:bg-white/5 hover:text-ink'
              )}
            >
              {active && (
                <>
                  <span className="absolute inset-0 -z-10 rounded-xl aurora-grad opacity-90 shadow-lg shadow-violet-900/40" />
                  <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-full bg-white/80" />
                </>
              )}
              <item.icon
                className={cn(
                  'h-[18px] w-[18px] flex-shrink-0',
                  active ? 'text-white' : 'text-faint-ink group-hover:text-ink'
                )}
              />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4">
        <div className="mb-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
          <p className="text-[11px] text-faint-ink">Signed in as</p>
          <p className="truncate text-xs font-medium text-ink">admin@tektribe.io</p>
        </div>
        <button
          onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-ink transition-all hover:bg-white/5 hover:text-ink"
        >
          <LogOut className="h-[18px] w-[18px]" />
          Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen">
      {/* Mobile drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="fixed inset-y-0 left-0 w-64">
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute right-3 top-4 z-10 text-muted-ink hover:text-ink"
              aria-label="Close navigation"
            >
              <X className="h-6 w-6" />
            </button>
            <Sidebar />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <Sidebar />
      </div>

      {/* Main */}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-4 border-b border-white/10 bg-white/[0.03] px-6 backdrop-blur-xl">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-muted-ink hover:text-ink lg:hidden"
            aria-label="Open navigation"
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex-1" />
          <span className="pill text-emerald-300">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            Live
          </span>
          <div className="flex items-center gap-2 text-sm text-muted-ink">
            <Shield className="h-4 w-4 text-violet-300" />
            <span className="hidden sm:inline">Tek Tribe Admin</span>
          </div>
        </header>

        <main className="animate-fade-up p-6 lg:p-8">{children}</main>
      </div>
    </div>
  )
}
