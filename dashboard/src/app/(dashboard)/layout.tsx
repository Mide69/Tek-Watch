'use client'

import { DashboardProvider } from '@/contexts/DashboardContext'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'

export default function DashboardGroupLayout({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <DashboardProvider>
        {children}
      </DashboardProvider>
    </ErrorBoundary>
  )
}
