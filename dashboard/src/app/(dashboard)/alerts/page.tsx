'use client'

import { useState, useEffect, useCallback } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import {
  AlertTriangle, CheckCircle, Clock, Download, Zap,
  ChevronLeft, ChevronRight,
} from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard } from '@/contexts/DashboardContext'
import { useAlerts } from '@/hooks/useData'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 20

type AlertStatus = 'active' | 'acknowledged'
type Alert = {
  alert_id: string
  severity: string
  status: AlertStatus
  type: string
  service: string
  resource: string
  description: string
  triggered_at: string
  current_value?: number
  threshold_value?: number | null
  recommendation?: string
  acknowledged_at?: string
}

export default function AlertsPage() {
  const { customerId }      = useAuth()
  const { refreshKey }      = useDashboard()
  const [filter, setFilter] = useState<'all' | 'active' | 'acknowledged'>('all')
  const [page, setPage]     = useState(0)
  const [localAlerts, setLocalAlerts] = useState<Alert[]>([])

  const { data: alertsData, isLoading } = useAlerts(PAGE_SIZE, page * PAGE_SIZE)
  const total = alertsData?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  // Merge remote data into local state (preserves optimistic ack)
  useEffect(() => {
    if (alertsData?.alerts) setLocalAlerts(alertsData.alerts as Alert[])
  }, [alertsData, refreshKey])

  const displayed = filter === 'all'
    ? localAlerts
    : localAlerts.filter(a => a.status === filter)

  const active = localAlerts.filter(a => a.status === 'active').length
  const acked  = localAlerts.filter(a => a.status === 'acknowledged').length

  const handleAck = (id: string) => {
    setLocalAlerts(prev => prev.map(a =>
      a.alert_id === id
        ? { ...a, status: 'acknowledged' as AlertStatus, acknowledged_at: new Date().toISOString() }
        : a
    ))
  }

  const handleExport = useCallback(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'
    const params = filter !== 'all' ? `?status_filter=${filter}&format=csv` : '?format=csv'
    window.open(`${base}/api/v1/alerts/export${params}`, '_blank')
  }, [filter])

  if (isLoading && localAlerts.length === 0) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-4">
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
          {[0, 1, 2].map(i => <CardSkeleton key={i} />)}
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              Threshold breaches and AI-detected anomalies · {total} total
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Export */}
            <button
              onClick={handleExport}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>

            {/* Filter tabs */}
            <div className="flex gap-1 p-1 bg-muted border border-border rounded-xl">
              {[
                { key: 'all',          label: `All (${total})` },
                { key: 'active',       label: `Active (${active})` },
                { key: 'acknowledged', label: `Acked (${acked})` },
              ].map(f => (
                <button
                  key={f.key}
                  onClick={() => { setFilter(f.key as typeof filter); setPage(0) }}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    filter === f.key
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Alert list */}
        {displayed.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <CheckCircle className="h-12 w-12 text-emerald-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">No alerts</h3>
              <p className="text-muted-foreground text-sm">Your infrastructure looks healthy</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {displayed.map(alert => (
              <Card
                key={alert.alert_id}
                className={cn(
                  alert.status === 'acknowledged' && 'opacity-60',
                  alert.severity === 'critical' && alert.status !== 'acknowledged' && 'border-red-500/30',
                  alert.severity === 'warning'  && alert.status !== 'acknowledged' && 'border-amber-500/20',
                )}
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    {/* Severity bar */}
                    <div className={cn(
                      'w-1 self-stretch rounded-full flex-shrink-0',
                      alert.severity === 'critical' ? 'bg-red-500'
                        : alert.severity === 'warning' ? 'bg-amber-500'
                        : 'bg-blue-500'
                    )} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <Badge variant={
                          alert.severity === 'critical' ? 'error'
                            : alert.severity === 'warning' ? 'warning'
                            : 'info'
                        }>
                          {alert.severity.toUpperCase()}
                        </Badge>
                        {alert.type === 'ai_anomaly' && (
                          <Badge variant="ai">
                            <Zap className="w-3 h-3 mr-1 inline" />AI Detected
                          </Badge>
                        )}
                        <Badge variant="default">{alert.service}</Badge>
                        {alert.status === 'acknowledged' && (
                          <Badge variant="success">Acknowledged</Badge>
                        )}
                      </div>

                      <h3 className="font-semibold text-foreground mb-1.5">{alert.resource}</h3>
                      <p className="text-sm text-muted-foreground mb-3 leading-relaxed">
                        {alert.description}
                      </p>

                      {alert.type === 'threshold' && alert.current_value !== undefined && (
                        <div className="flex items-center gap-4 text-xs mb-3 flex-wrap">
                          <div className="px-2.5 py-1.5 rounded-lg bg-muted border border-border">
                            <span className="text-muted-foreground">Current: </span>
                            <span className="font-semibold text-foreground">
                              {alert.current_value.toFixed(1)}
                            </span>
                          </div>
                          {alert.threshold_value != null && (
                            <div className="px-2.5 py-1.5 rounded-lg bg-muted border border-border">
                              <span className="text-muted-foreground">Threshold: </span>
                              <span className="font-semibold text-foreground">
                                {alert.threshold_value}
                              </span>
                            </div>
                          )}
                        </div>
                      )}

                      {alert.recommendation && (
                        <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 mb-3">
                          <span className="text-xs font-semibold text-primary">Recommendation</span>
                          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                            {alert.recommendation}
                          </p>
                        </div>
                      )}

                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        Triggered {formatRelativeTime(alert.triggered_at)}
                        {alert.acknowledged_at && (
                          <> · Acked {formatRelativeTime(alert.acknowledged_at)}</>
                        )}
                      </div>
                    </div>

                    {alert.status === 'active' && (
                      <button
                        onClick={() => handleAck(alert.alert_id)}
                        className="flex-shrink-0 px-3 py-1.5 text-xs font-semibold border border-primary/30 text-primary hover:bg-primary hover:text-primary-foreground rounded-lg transition-all"
                      >
                        Acknowledge
                      </button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <p className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages} · {total} total alerts
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Prev
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                Next
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

      </div>
    </DashboardLayout>
  )
}
