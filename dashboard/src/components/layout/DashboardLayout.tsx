'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  Activity, AlertTriangle, Database, DollarSign, Globe,
  HardDrive, LayoutDashboard, LogOut, Mail, Menu,
  Server, Shield, X, Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'

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
]

// Demo mode when explicitly set OR when no real Cognito pool is configured
const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''
const DEMO_MODE = (
  process.env.NEXT_PUBLIC_DEMO_MODE === 'true' ||
  COGNITO_POOL.length === 0 ||
  COGNITO_POOL.includes('placeholder') ||
  COGNITO_POOL === 'undefined'
)

export default function DashboardLayout({ children, customerId }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()
  const router = useRouter()

  const handleSignOut = async () => {
    if (DEMO_MODE) { router.push('/'); return }
    const { authSignOut } = await import('@/lib/auth')
    await authSignOut()
    router.push('/login')
  }

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center gap-3 h-16 px-5 border-b border-white/[0.06]">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <Radio className="w-4 h-4 text-white" />
        </div>
        <span className="text-base font-bold text-white tracking-tight">Tek Watch</span>
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
                  ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]'
              )}
            >
              <item.icon className={cn('h-4 w-4 flex-shrink-0', isActive ? 'text-indigo-400' : 'text-slate-500')} />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 pb-4 border-t border-white/[0.06] pt-4 space-y-3">
        {customerId && (
          <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
            <p className="text-xs text-slate-500 mb-0.5">Customer ID</p>
            <p className="text-sm font-mono font-semibold text-slate-300">{customerId}</p>
          </div>
        )}
        <button
          onClick={handleSignOut}
          className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] transition-colors"
        >
          <LogOut className="h-4 w-4" />
          {DEMO_MODE ? 'Back to Home' : 'Sign out'}
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <div className="fixed inset-y-0 left-0 w-64 bg-[#0a0f1e] border-r border-white/[0.06]">
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent />
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col bg-[#0a0f1e] border-r border-white/[0.06]">
        <SidebarContent />
      </div>

      {/* Main content */}
      <div className="lg:pl-64 flex flex-col min-h-screen">
        {/* Top bar */}
        <div className="sticky top-0 z-40 flex h-14 items-center gap-4 border-b border-white/[0.06] bg-background/80 backdrop-blur-sm px-4 lg:px-6">
          <button onClick={() => setSidebarOpen(true)} className="lg:hidden text-slate-400 hover:text-white">
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-3">
            {/* Live indicator */}
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              LIVE
            </div>
            <select className="px-3 py-1.5 text-xs border border-white/[0.08] rounded-lg bg-white/[0.04] text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500">
              <option value="">All Regions</option>
              <option value="eu-west-2">eu-west-2</option>
              <option value="eu-west-1">eu-west-1</option>
              <option value="us-east-1">us-east-1</option>
            </select>
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
