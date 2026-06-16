'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Activity, AlertTriangle, Database, DollarSign, Globe,
  HardDrive, LayoutDashboard, LogOut, Mail, Menu, MessageSquare,
  RefreshCw, Server, Shield, X, Radio, CheckCircle,
  AlertCircle, Info, XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { isDemoMode } from '@/lib/demoMode'
import {
  useDashboard,
  TIME_RANGE_OPTIONS, type TimeRange, type Region,
} from '@/contexts/DashboardContext'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { NotificationBell } from '@/components/ui/NotificationBell'

interface DashboardLayoutProps {
  children: React.ReactNode
  customerId?: string | null
}

const navigation = [
  { name: 'Overview',   href: '/overview',   icon: LayoutDashboard },
  { name: 'Compute',    href: '/compute',    icon: Server },
  { name: 'Databases',  href: '/databases',  icon: Database },
  { name: 'Networking', href: '/networking', icon: Globe },
  { name: 'Storage',    href: '/storage',    icon: HardDrive },
  { name: 'Messaging',  href: '/messaging',  icon: Mail },
  { name: 'Security',   href: '/security',   icon: Shield },
  { name: 'Cost',       href: '/cost',       icon: DollarSign },
  { name: 'Alerts',     href: '/alerts',     icon: AlertTriangle },
  { name: 'Agent',      href: '/agent',      icon: Activity },
  { name: 'Ask AI',     href: '/chat',       icon: MessageSquare },
]

const DEMO_MODE = isDemoMode()

// ─── Toast ────────────────────────────────────────────────────────────────────

function ToastContainer() {
  const { toasts, removeToast } = useDashboard()
  if (toasts.length === 0) return null
  const icons = {
    success: <CheckCircle className="w-4 h-4 text-emerald-500" />,
    warning: <AlertCircle className="w-4 h-4 text-amber-500" />,
    error:   <XCircle     className="w-4 h-4 text-red-500"    />,
    info:    <Info        className="w-4 h-4 text-blue-500"   />,
  }
  return (
    <div className="fixed bottom-4 right-4 z-[9999] space-y-2 max-w-sm w-full pointer-events-none">
      {toasts.map(t => (
        <div key={t.id}
          className="flex items-start gap-3 p-4 rounded-xl border border-border bg-card shadow-lg pointer-events-auto animate-fade-in"
        >
          {icons[t.type]}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground">{t.title}</p>
            {t.message && <p className="text-xs text-muted-foreground mt-0.5">{t.message}</p>}
          </div>
          <button onClick={() => removeToast(t.id)} aria-label="Dismiss notification" className="text-muted-foreground hover:text-foreground">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}

// ─── Inner layout (has DashboardContext) ──────────────────────────────────────

function Inner({ children, customerId }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()
  const router   = useRouter()
  const {
    timeRange, setTimeRange,
    region, setRegion,
    secondsToRefresh, refresh, isRefreshing, lastUpdated,
  } = useDashboard()

  const handleSignOut = useCallback(async () => {
    if (DEMO_MODE) { router.push('/'); return }
    const { authSignOut } = await import('@/lib/auth')
    await authSignOut()
    router.push('/login')
  }, [router])

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 h-16 px-5 border-b border-sidebar-border">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm">
          <Radio className="w-4 h-4 text-white" />
        </div>
        <span className="text-base font-bold text-sidebar-foreground tracking-tight">Tek Watch</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={() => setSidebarOpen(false)}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                isActive
                  ? 'bg-primary/10 text-primary border border-primary/20'
                  : 'text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-hover'
              )}
            >
              <item.icon className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-primary' : 'text-sidebar-muted')} />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 pb-4 border-t border-sidebar-border pt-4 space-y-3">
        {customerId && (
          <div className="px-3 py-2 rounded-lg bg-muted border border-border">
            <p className="text-xs text-muted-foreground mb-0.5">Customer ID</p>
            <p className="text-sm font-mono font-semibold text-foreground">{customerId}</p>
          </div>
        )}
        <div className="px-3 py-1.5 text-xs text-muted-foreground/60" suppressHydrationWarning>
          Updated {lastUpdated.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium rounded-lg text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-hover transition-colors"
        >
          <LogOut className="h-4 w-4" />
          {DEMO_MODE ? 'Back to Home' : 'Sign out'}
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="fixed inset-y-0 left-0 w-64 bg-sidebar border-r border-sidebar-border shadow-xl">
            <button onClick={() => setSidebarOpen(false)} aria-label="Close navigation" className="absolute top-4 right-4 text-muted-foreground hover:text-foreground">
              <X className="h-5 w-5" />
            </button>
            <SidebarContent />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col bg-sidebar border-r border-sidebar-border">
        <SidebarContent />
      </div>

      {/* Main content area */}
      <div className="lg:pl-64 flex flex-col min-h-screen">

        {/* Top bar */}
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/90 backdrop-blur-sm px-4 lg:px-6">
          <button onClick={() => setSidebarOpen(true)} aria-label="Open navigation" className="lg:hidden text-muted-foreground hover:text-foreground">
            <Menu className="h-5 w-5" />
          </button>

          <div className="flex-1" />

          {/* Time range picker */}
          <div className="hidden sm:flex items-center gap-0.5 bg-muted border border-border rounded-lg p-0.5">
            {TIME_RANGE_OPTIONS.map(r => (
              <button
                key={r}
                onClick={() => setTimeRange(r as TimeRange)}
                className={cn(
                  'px-2.5 py-1 text-xs font-medium rounded-md transition-all',
                  timeRange === r
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {r.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Region picker */}
          <select
            value={region}
            onChange={e => setRegion(e.target.value as Region)}
            aria-label="Filter by AWS region"
            className="px-3 py-1.5 text-xs border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Regions</option>
            <option value="eu-west-2">eu-west-2</option>
            <option value="eu-west-1">eu-west-1</option>
            <option value="us-east-1">us-east-1</option>
          </select>

          {/* Refresh */}
          <button
            onClick={refresh}
            aria-label={`Refresh data — auto-refreshing in ${secondsToRefresh}s`}
            title={`Auto-refresh in ${secondsToRefresh}s`}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className={cn('w-3.5 h-3.5', isRefreshing && 'animate-spin text-primary')} />
            <span className="hidden md:inline tabular-nums">{secondsToRefresh}s</span>
          </button>

          {/* Live indicator */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-60" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            LIVE
          </div>

          {/* Notification bell */}
          <NotificationBell />

          {/* Theme toggle */}
          <ThemeToggle />
        </header>

        {/* Mobile time range bar */}
        <div className="sm:hidden flex items-center gap-1 px-4 py-2 border-b border-border bg-background/60 overflow-x-auto">
          {TIME_RANGE_OPTIONS.map(r => (
            <button
              key={r}
              onClick={() => setTimeRange(r as TimeRange)}
              className={cn(
                'flex-shrink-0 px-3 py-1 text-xs font-medium rounded-md transition-all',
                timeRange === r ? 'bg-primary text-primary-foreground' : 'text-muted-foreground bg-muted'
              )}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Page content — theme-page enables CSS cascade for page internals */}
        <main className="flex-1 p-4 lg:p-6 theme-page">
          {children}
        </main>
      </div>

      <ToastContainer />
    </div>
  )
}

// ─── Exported wrapper ─────────────────────────────────────────────────────────

export default function DashboardLayout({ children, customerId }: DashboardLayoutProps) {
  return <Inner customerId={customerId}>{children}</Inner>
}
