'use client'

/**
 * ResourceDetailPanel — slide-over panel showing time-series charts
 * and metadata for a selected AWS resource.
 */
import { useEffect, useState } from 'react'
import { X, Clock, Activity } from 'lucide-react'
import TimeSeriesChart from '@/components/charts/TimeSeriesChart'
import apiClient from '@/lib/api'
import { cn } from '@/lib/utils'

type TimeRange = '24h' | '7d' | '30d' | '90d'

interface ResourceDetailPanelProps {
  resourceId: string | null
  resourceName?: string
  service?: string
  metricName?: string
  onClose: () => void
}

const TIME_RANGES: { label: string; value: TimeRange }[] = [
  { label: '24h', value: '24h' },
  { label: '7d',  value: '7d'  },
  { label: '30d', value: '30d' },
  { label: '90d', value: '90d' },
]

export default function ResourceDetailPanel({
  resourceId,
  resourceName,
  service,
  metricName = 'cpu_utilization_percent',
  onClose,
}: ResourceDetailPanelProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h')
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!resourceId) return
    fetchMetrics()
  }, [resourceId, timeRange, metricName]) // eslint-disable-line react-hooks/exhaustive-deps

  const fetchMetrics = async () => {
    if (!resourceId) return
    setLoading(true)
    try {
      const response = await apiClient.getResourceMetrics(resourceId, metricName, timeRange)
      setData(response.data || [])
    } catch (err) {
      console.error('Failed to fetch resource metrics:', err)
      setData([])
    } finally {
      setLoading(false)
    }
  }

  if (!resourceId) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Resource details: ${resourceName || resourceId}`}
        className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-background border-l shadow-xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-semibold truncate max-w-xs">
              {resourceName || resourceId}
            </h2>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">
              {resourceId}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-md hover:bg-accent transition-colors"
            aria-label="Close panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Time range selector */}
        <div className="flex items-center gap-1 px-6 py-3 border-b bg-muted/30">
          <Clock className="h-4 w-4 text-muted-foreground mr-1" />
          {TIME_RANGES.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setTimeRange(value)}
              className={cn(
                'px-3 py-1 text-sm rounded-md transition-colors',
                timeRange === value
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent text-muted-foreground'
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Chart */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-medium capitalize">
                {metricName.replace(/_/g, ' ')}
              </h3>
            </div>
            <TimeSeriesChart
              data={data}
              dataKey="value"
              color="#3b82f6"
              height={220}
              type="area"
              loading={loading}
              formatValue={(v) => `${v.toFixed(2)}`}
            />
          </div>

          {/* Resource info */}
          <div className="border rounded-lg p-4 space-y-2">
            <h3 className="text-sm font-semibold mb-3">Resource Info</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <span className="text-muted-foreground">Resource ID</span>
              <span className="font-mono text-xs truncate">{resourceId}</span>
              {resourceName && (
                <>
                  <span className="text-muted-foreground">Name</span>
                  <span>{resourceName}</span>
                </>
              )}
              {service && (
                <>
                  <span className="text-muted-foreground">Service</span>
                  <span className="uppercase text-xs font-medium">{service}</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
