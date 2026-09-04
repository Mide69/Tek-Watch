'use client'

import { DashboardProvider } from '@/contexts/DashboardContext'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { AuthProvider } from '@/hooks/useAuth'

// AuthProvider lives here, not in each page, specifically because this
// layout is the one thing that survives every navigation within the
// dashboard — every page.tsx below it is torn down and rebuilt on each
// route change. Mounting the Cognito check here means it resolves once per
// session instead of racing itself on every click. See the long comment in
// hooks/useAuth.tsx for what that race actually did.
export default function DashboardGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <DashboardProvider>
          {children}
        </DashboardProvider>
      </AuthProvider>
    </ErrorBoundary>
  )
}
