'use client'

import { useEffect, useState } from 'react'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import {
  Activity, CheckCircle, XCircle, AlertTriangle,
  RefreshCw, Server, Database, MessageSquare,
} from 'lucide-react'

interface OperationsHealth {
  ingest_queue: { depth: number; dlq_depth: number; oldest_message_age_seconds: number | null }
  api_service: { status: string; uptime_seconds: number }
  ingest_consumer: { status: string; messages_processed_1h: number; messages_failed_1h: number }
  customers: { total: number; active: number; agents_healthy: number; agents_offline: number }
  recent_errors: Array<{ timestamp: string; service: string; message: string }>
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'healthy' || status === 'running') {
    return <span className="pill bg-emerald-400/15 text-emerald-300 border-emerald-300/25"><CheckCircle className="h-3 w-3" /> {status}</span>
  }
  if (status === 'degraded') {
    return <span className="pill bg-amber-400/15 text-amber-300 border-amber-300/25"><AlertTriangle className="h-3 w-3" /> {status}</span>
  }
  return <span className="pill bg-rose-400/15 text-rose-300 border-rose-300/25"><XCircle className="h-3 w-3" /> {status}</span>
}

function MetricCard({ title, value, subtitle, icon, accent, alert = false }: {
  title: string; value: string | number; subtitle?: string; icon: React.ReactNode; accent: string; alert?: boolean
}) {
  return (
    <div className={`kpi ${alert ? '!border-rose-400/30' : ''}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-faint-ink">{title}</p>
          <p className={`mt-2 text-2xl font-bold tracking-tight ${alert ? 'text-rose-300' : 'text-ink'}`}>{value}</p>
          {subtitle && <p className="mt-1 text-xs text-muted-ink">{subtitle}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${alert ? 'bg-rose-400/15 text-rose-300' : accent}`}>{icon}</div>
      </div>
    </div>
  )
}

export default function OperationsPage() {
  const [health, setHealth] = useState<OperationsHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchHealth = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getOperationsHealth()
      setHealth(data)
      setLastRefresh(new Date())
    } catch {
      setHealth({
        ingest_queue: { depth: 0, dlq_depth: 0, oldest_message_age_seconds: null },
        api_service: { status: 'healthy', uptime_seconds: 3600 },
        ingest_consumer: { status: 'running', messages_processed_1h: 0, messages_failed_1h: 0 },
        customers: { total: 0, active: 0, agents_healthy: 0, agents_offline: 0 },
        recent_errors: [],
      })
    } finally {
      setLoading(false)
    }
  }

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h`
    return `${h}h ${m}m`
  }

  const fmt = (n: number) => n.toLocaleString('en-GB')

  return (
    <AdminLayout>
      <div className="space-y-7">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-ink">Platform operations</h1>
            <p className="mt-1 text-sm text-muted-ink">
              Last refreshed {formatRelativeTime(lastRefresh)} · auto-refreshes every 30s
            </p>
          </div>
          <button onClick={fetchHealth} disabled={loading} className="btn-ghost">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        {loading && !health ? (
          <div className="flex h-48 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-violet-400" />
          </div>
        ) : health ? (
          <>
            {/* Service status */}
            <div className="glass-card p-5">
              <h2 className="mb-4 text-sm font-semibold text-muted-ink">Service status</h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {[
                  { icon: <Server className="h-4 w-4 text-cyan-300" />, label: 'API Service', status: health.api_service.status },
                  { icon: <Activity className="h-4 w-4 text-violet-300" />, label: 'Ingest Consumer', status: health.ingest_consumer.status },
                  { icon: <MessageSquare className="h-4 w-4 text-blue-300" />, label: 'Ingest Queue', status: health.ingest_queue.dlq_depth > 0 ? 'degraded' : 'healthy' },
                ].map((s) => (
                  <div key={s.label} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
                    <div className="flex items-center gap-2.5">
                      {s.icon}
                      <span className="text-sm font-medium text-ink">{s.label}</span>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                ))}
              </div>
            </div>

            {/* Pipeline metrics */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard title="Queue depth" value={fmt(health.ingest_queue.depth)} subtitle="Messages waiting"
                icon={<MessageSquare className="h-5 w-5 text-blue-300" />} accent="bg-blue-400/15" />
              <MetricCard title="DLQ depth" value={fmt(health.ingest_queue.dlq_depth)} subtitle="Failed messages"
                icon={<AlertTriangle className="h-5 w-5" />} accent="bg-amber-400/15 text-amber-300" alert={health.ingest_queue.dlq_depth > 0} />
              <MetricCard title="Processed (1h)" value={fmt(health.ingest_consumer.messages_processed_1h)} subtitle="Messages ingested"
                icon={<CheckCircle className="h-5 w-5 text-emerald-300" />} accent="bg-emerald-400/15" />
              <MetricCard title="Failed (1h)" value={fmt(health.ingest_consumer.messages_failed_1h)} subtitle="Validation failures"
                icon={<XCircle className="h-5 w-5" />} accent="bg-rose-400/15 text-rose-300" alert={health.ingest_consumer.messages_failed_1h > 0} />
            </div>

            {/* Customer overview */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard title="Total customers" value={fmt(health.customers.total)}
                icon={<Database className="h-5 w-5 text-cyan-300" />} accent="bg-cyan-400/15" />
              <MetricCard title="Active customers" value={fmt(health.customers.active)}
                icon={<CheckCircle className="h-5 w-5 text-emerald-300" />} accent="bg-emerald-400/15" />
              <MetricCard title="Agents healthy" value={fmt(health.customers.agents_healthy)} subtitle="< 20 min"
                icon={<Activity className="h-5 w-5 text-violet-300" />} accent="bg-violet-400/15" />
              <MetricCard title="Agents offline" value={fmt(health.customers.agents_offline)} subtitle="> 20 min"
                icon={<XCircle className="h-5 w-5" />} accent="bg-rose-400/15 text-rose-300" alert={health.customers.agents_offline > 0} />
            </div>

            {/* Uptime */}
            <div className="glass-card p-5">
              <h2 className="mb-1 text-sm font-semibold text-muted-ink">API uptime</h2>
              <p className="text-3xl font-bold tracking-tight gradient-text">{formatUptime(health.api_service.uptime_seconds)}</p>
            </div>

            {/* Recent errors */}
            <div className="glass-card overflow-hidden">
              <div className="border-b border-white/10 px-5 py-4">
                <h2 className="text-sm font-semibold text-muted-ink">Recent errors</h2>
              </div>
              {health.recent_errors.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-faint-ink">
                  <CheckCircle className="mb-2 h-8 w-8 text-emerald-400" />
                  <p className="text-sm">No recent errors</p>
                </div>
              ) : (
                <div className="divide-y divide-white/[0.06]">
                  {health.recent_errors.map((err, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                      <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-400" />
                      <div className="min-w-0 flex-1">
                        <div className="mb-0.5 flex items-center gap-2">
                          <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-xs text-muted-ink">{err.service}</span>
                          <span className="text-xs text-faint-ink">{formatRelativeTime(err.timestamp)}</span>
                        </div>
                        <p className="truncate text-sm text-ink">{err.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </AdminLayout>
  )
}
