'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Activity, AlertTriangle, Database, DollarSign, Globe,
  HardDrive, LayoutDashboard, LogOut, Mail, Menu, MessageSquare,
  Home, RefreshCw, Server, Settings, Shield, X, CheckCircle,
  AlertCircle, Info, XCircle,
} from 'lucide-react'
import { LogoMark } from '@/components/ui/Logo'
import { cn } from '@/lib/utils'
import { isDemoBuild, isDemoSession, endDemoSession } from '@/lib/demoMode'
import { useFixtureView } from '@/hooks/useFixtureView'
import {
  useDashboard,
  TIME_RANGE_OPTIONS, type TimeRange, type Region,
} from '@/contexts/DashboardContext'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { NotificationBell } from '@/components/ui/NotificationBell'
import { HistoryNav } from '@/components/ui/HistoryNav'
import { DemoBadge } from '@/components/ui/DemoBadge'
import { SampleDataBanner } from '@/components/ui/SampleDataBanner'
import { ConfigErrorBanner } from '@/components/ui/ConfigErrorBanner'
import { useProfile } from '@/hooks/useProfile'
import apiClient from '@/lib/api'

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
  { name: 'Assistant',  href: '/chat',       icon: MessageSquare },
  { name: 'Settings',   href: '/settings',   icon: Settings },
]

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

  // Company identity for the sidebar. Returns null when there is no token yet
  // (demo visitors, first paint), which just falls back to the Customer ID.
  const { data: profile } = useProfile()
  // Asked per render, not once at import: signing in ends a demo.
  const DEMO_MODE = useFixtureView()

  const handleSignOut = useCallback(async () => {
    // Leaving a demo tab ends the demo and nothing else: a visitor has no
    // session, and someone signed in who was only looking should still be
    // signed in afterwards.
    if (isDemoSession()) {
      endDemoSession()
      router.push('/')
      return
    }
    // A demo build has no Cognito to sign out of.
    if (isDemoBuild()) { router.push('/'); return }

    const { authSignOut } = await import('@/lib/auth')
    try {
      await authSignOut()
    } finally {
      // Even if Cognito rejects the call, the local session must not survive a
      // sign-out. Leaving the token behind would put them straight back in.
      apiClient.clearToken()
      router.push('/login')
    }
  }, [router])

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 h-16 px-5 border-b border-sidebar-border">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0 shadow-sm">
          <LogoMark className="w-4 h-4 text-white" />
        </div>
        <span className="text-base font-bold tracking-tight">
          <span className="text-sidebar-foreground">Tek</span><span className="text-primary">Watch</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
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
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-muted border border-border">
            {profile?.logo_url && (
              // Presigned, time-limited S3 url — plain <img>, since this is a
              // static export with no image optimiser running.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={profile.logo_url}
                alt=""
                className="w-8 h-8 rounded-md object-contain flex-shrink-0 bg-background"
              />
            )}
            <div className="min-w-0">
              {/* Company name if they have set one, Customer ID otherwise. The
                  ID stays on the second line either way: support asks for it,
                  and hiding it entirely just moves the problem. */}
              <p className="text-sm font-semibold text-foreground truncate">
                {profile?.display_name || customerId}
              </p>
              {/* Only when it adds something. With no company name set,
                  display_name IS the Customer ID, and printing it twice looks
                  like a bug. */}
              {profile?.display_name && profile.display_name !== customerId ? (
                <p className="text-xs font-mono text-muted-foreground truncate">{customerId}</p>
              ) : (
                <p className="text-xs text-muted-foreground">Customer ID</p>
              )}
            </div>
          </div>
        )}
        <div className="px-3 py-1.5 text-xs text-muted-foreground/60" suppressHydrationWarning>
          Updated {lastUpdated.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
        {/* Two separate things. One button did whichever the app had guessed,
            so a signed-in customer whose session was mistaken for a demo got
            "Back to Home" and no way to sign out at all — and nobody could
            reach the marketing site without losing their session. Going home
            and leaving your account are not the same action. */}
        <Link
          href="/"
          className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium rounded-lg text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-hover transition-colors"
        >
          <Home className="h-4 w-4" />
          Home
        </Link>
        <button
          onClick={handleSignOut}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium rounded-lg text-sidebar-muted hover:text-sidebar-foreground hover:bg-sidebar-hover transition-colors"
        >
          <LogOut className="h-4 w-4" />
          {DEMO_MODE ? 'Exit demo' : 'Sign out'}
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

        {/* Top bar.
            overflow-x-auto, not overflow visible: on a narrow phone in demo
            mode, the hamburger, history arrows, demo badge, region picker,
            refresh, alerts and theme toggle together are wider than the
            viewport. Nothing here was cut, so the row's own intrinsic width
            was dragging the whole page into horizontal scroll — the same
            overflow-x-auto pattern the mobile time-range bar below already
            uses, now applied one level up so the bar scrolls within itself
            instead of the page scrolling around it. */}
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 overflow-x-auto border-b border-border bg-background/90 backdrop-blur-sm px-4 lg:px-6">
          <button onClick={() => setSidebarOpen(true)} aria-label="Open navigation" className="lg:hidden text-muted-foreground hover:text-foreground">
            <Menu className="h-5 w-5" />
          </button>

          <HistoryNav />

          <DemoBadge />

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

          {/* There was a pinging "LIVE" badge here. The agent reports every
              fifteen minutes, so it overstated the data as well as looking like
              a template. The refresh countdown beside it says what is true. */}

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

        {/* Page content — theme-page enables CSS cascade for page internals.
            min-w-0 matters here: a flex item's default min-width is auto, not
            0, so without it main refuses to shrink below the intrinsic width
            of whatever it contains. A wide table wrapped in its own
            overflow-x-auto div still has an intrinsic width, and that width
            was propagating up through main and out to the page body — the
            table's own scroll container worked, but the whole page scrolled
            sideways around it on any viewport narrower than the table. */}
        <main className="flex-1 min-w-0 p-4 lg:p-6 theme-page">
          <ConfigErrorBanner />
          <SampleDataBanner />
          {/* Nothing paints until we know whose data this is. It costs one
              frame and removes the window in which a signed-in customer was
              shown the sample estate — the flash on every page transition.
              The skeleton is what the server prerenders too, so there is no
              hydration mismatch to trade for it. */}
          {DEMO_MODE === null
            ? <div className="h-64 rounded-xl bg-muted/40 animate-pulse" aria-hidden />
            : children}
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
