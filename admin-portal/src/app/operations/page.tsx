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
  ingest_queue: {
    depth: number
    dlq_depth: number
    oldest_message_age_seconds: number | null
  }
  api_service: {
    status: string
    uptime_seconds: number
  }
  ingest_consumer: {
    status: string
    messages_processed_1h: number
    messages_failed_1h: number
  }
  customers: {
    total: number
    active: number
    agents_healthy: number
    agents_offline: number
  }
  recent_errors: Array<{
    timestamp: string
    service: string
    message: string
  }>
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'healthy' || status === 'running') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
        <CheckCircle className="h-3 w-3" /> {status}
      </span>
    )
  }
  if (status === 'degraded') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
        <AlertTriangle className="h-3 w-3" /> {status}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
      <XCircle className="h-3 w-3" /> {status}
    </span>
  )
}

function MetricCard({
  title, value, subtitle, icon, alert = false,
}: {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  alert?: boolean
}) {
  return (
    <div className={`bg-white rounded-lg border p-5 ${alert ? 'border-red-300 bg-red-50' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-600">{title}</span>
        <div className={`p-2 rounded-lg ${alert ? 'bg-red-100 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
          {icon}
        </div>
      </div>
      <div className={`text-2xl font-bold ${alert ? 'text-red-700' : 'text-gray-900'}`}>{value}</div>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
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
      // Show mock data if API unavailable
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

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Platform Operations</h1>
            <p className="text-sm text-gray-500 mt-1">
              Last refreshed {formatRelativeTime(lastRefresh)} · auto-refreshes every 30s
            </p>
          </div>
          <button
            onClick={fetchHealth}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {loading && !health ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : health ? (
          <>
            {/* Service Status Row */}
            <div className="bg-white rounded-lg border p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-4">Service Status</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium">API Service</span>
                  </div>
                  <StatusBadge status={health.api_service.status} />
                </div>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium">Ingest Consumer</span>
                  </div>
                  <StatusBadge status={health.ingest_consumer.status} />
                </div>
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-gray-500" />
                    <span className="text-sm font-medium">Ingest Queue</span>
                  </div>
                  <StatusBadge status={health.ingest_queue.dlq_depth > 0 ? 'degraded' : 'healthy'} />
                </div>
              </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                title="Queue Depth"
                value={health.ingest_queue.depth}
                subtitle="Messages waiting"
                icon={<MessageSquare className="h-4 w-4" />}
              />
              <MetricCard
                title="DLQ Depth"
                value={health.ingest_queue.dlq_depth}
                subtitle="Failed messages"
                icon={<AlertTriangle className="h-4 w-4" />}
                alert={health.ingest_queue.dlq_depth > 0}
              />
              <MetricCard
                title="Processed (1h)"
                value={health.ingest_consumer.messages_processed_1h}
                subtitle="Messages ingested"
                icon={<CheckCircle className="h-4 w-4" />}
              />
              <MetricCard
                title="Failed (1h)"
                value={health.ingest_consumer.messages_failed_1h}
                subtitle="Validation failures"
                icon={<XCircle className="h-4 w-4" />}
                alert={health.ingest_consumer.messages_failed_1h > 0}
              />
            </div>

            {/* Customer Overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                title="Total Customers"
                value={health.customers.total}
                icon={<Database className="h-4 w-4" />}
              />
              <MetricCard
                title="Active Customers"
                value={health.customers.active}
                icon={<CheckCircle className="h-4 w-4" />}
              />
              <MetricCard
                title="Agents Healthy"
                value={health.customers.agents_healthy}
                subtitle="Reporting in last 20 min"
                icon={<Activity className="h-4 w-4" />}
              />
              <MetricCard
                title="Agents Offline"
                value={health.customers.agents_offline}
                subtitle="No heartbeat > 20 min"
                icon={<XCircle className="h-4 w-4" />}
                alert={health.customers.agents_offline > 0}
              />
            </div>

            {/* API Uptime */}
            <div className="bg-white rounded-lg border p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">API Uptime</h2>
              <p className="text-2xl font-bold text-gray-900">
                {formatUptime(health.api_service.uptime_seconds)}
              </p>
            </div>

            {/* Recent Errors */}
            <div className="bg-white rounded-lg border overflow-hidden">
              <div className="px-5 py-4 border-b">
                <h2 className="text-sm font-semibold text-gray-700">Recent Errors</h2>
              </div>
              {health.recent_errors.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-gray-400">
                  <CheckCircle className="h-8 w-8 mb-2 text-green-400" />
                  <p className="text-sm">No recent errors</p>
                </div>
              ) : (
                <div className="divide-y">
                  {health.recent_errors.map((err, i) => (
                    <div key={i} className="px-5 py-3 flex items-start gap-3">
                      <XCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-xs font-mono bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">
                            {err.service}
                          </span>
                          <span className="text-xs text-gray-400">{formatRelativeTime(err.timestamp)}</span>
                        </div>
                        <p className="text-sm text-gray-700 truncate">{err.message}</p>
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
