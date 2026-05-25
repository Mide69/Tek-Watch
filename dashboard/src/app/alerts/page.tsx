'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard } from '@/contexts/DashboardContext'
import { useAlerts } from '@/hooks/useData'

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
  const { data, isLoading } = useAlerts()
  const [filter, setFilter] = useState<'all' | 'active' | 'acknowledged'>('all')
  const [localAlerts, setLocalAlerts] = useState<Alert[]>([])

  // Sync local state when remote data changes (e.g. on refresh)
  useEffect(() => {
    if (data) setLocalAlerts(data as Alert[])
  }, [data, refreshKey])

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

  if (isLoading) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-4">
          <div className="h-8 w-32 bg-white/[0.06] rounded animate-pulse" />
          {[0,1,2].map(i => <CardSkeleton key={i} />)}
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white">Alerts</h1>
            <p className="text-slate-400 text-sm mt-0.5">Threshold breaches and AI-detected anomalies</p>
          </div>
          <div className="flex gap-1 p-1 bg-white/[0.03] border border-white/[0.06] rounded-xl">
            {[
              { key: 'all',          label: `All (${localAlerts.length})` },
              { key: 'active',       label: `Active (${active})` },
              { key: 'acknowledged', label: `Acked (${acked})` },
            ].map(f => (
              <button key={f.key} onClick={() => setFilter(f.key as typeof filter)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  filter === f.key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                }`}>
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {displayed.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <CheckCircle className="h-12 w-12 text-emerald-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-white mb-2">No alerts</h3>
              <p className="text-slate-400 text-sm">Your infrastructure looks healthy</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {displayed.map(alert => (
              <Card
                key={alert.alert_id}
                className={
                  alert.status === 'acknowledged' ? 'opacity-70' :
                  alert.severity === 'critical' ? 'border-red-500/30' : 'border-amber-500/20'
                }
              >
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    {/* Severity bar */}
                    <div className={`w-1 self-stretch rounded-full flex-shrink-0 ${
                      alert.severity === 'critical' ? 'bg-red-500' :
                      alert.severity === 'warning'  ? 'bg-amber-500' : 'bg-blue-500'
                    }`} />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-2">
                        <Badge variant={alert.severity === 'critical' ? 'error' : alert.severity === 'warning' ? 'warning' : 'info'}>
                          {alert.severity.toUpperCase()}
                        </Badge>
                        {alert.type === 'ai_anomaly' && (
                          <Badge variant="ai"><Zap className="w-3 h-3 mr-1 inline" />AI Detected</Badge>
                        )}
                        <Badge variant="default">{alert.service}</Badge>
                        {alert.status === 'acknowledged' && <Badge variant="success">Acknowledged</Badge>}
                      </div>

                      <h3 className="font-semibold text-white mb-1.5">{alert.resource}</h3>
                      <p className="text-sm text-slate-400 mb-3 leading-relaxed">{alert.description}</p>

                      {alert.type === 'threshold' && alert.current_value !== undefined && (
                        <div className="flex items-center gap-4 text-xs mb-3 flex-wrap">
                          <div className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                            <span className="text-slate-500">Current: </span>
                            <span className="font-semibold text-white">{alert.current_value.toFixed(1)}</span>
                          </div>
                          {alert.threshold_value != null && (
                            <div className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                              <span className="text-slate-500">Threshold: </span>
                              <span className="font-semibold text-slate-300">{alert.threshold_value}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {alert.recommendation && (
                        <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 mb-3">
                          <span className="text-xs font-semibold text-indigo-400">Recommendation</span>
                          <p className="text-xs text-slate-300 mt-1 leading-relaxed">{alert.recommendation}</p>
                        </div>
                      )}

                      <div className="flex items-center gap-1 text-xs text-slate-500">
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
                        className="flex-shrink-0 px-3 py-1.5 text-xs font-semibold border border-indigo-500/30 text-indigo-400 hover:bg-indigo-600 hover:text-white rounded-lg transition-all"
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
      </div>
    </DashboardLayout>
  )
}
