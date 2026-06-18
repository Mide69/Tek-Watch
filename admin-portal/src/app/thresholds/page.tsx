'use client'

import { useEffect, useState } from 'react'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { Save, RefreshCw, Plus } from 'lucide-react'

interface Threshold {
  PK: string
  SK: string
  service: string
  metric_name: string
  operator: string
  threshold_value: number
  severity: string
  enabled: boolean
}

const SERVICES = ['ec2', 'rds', 'lambda', 'ecs', 'sqs', 'dynamodb', 'elasticache']
const OPERATORS = [
  { value: 'gt', label: '> Greater than' },
  { value: 'gte', label: '≥ Greater than or equal' },
  { value: 'lt', label: '< Less than' },
  { value: 'lte', label: '≤ Less than or equal' },
]
const SEVERITIES = ['low', 'medium', 'high', 'critical']

const SEVERITY_BADGE: Record<string, string> = {
  low: 'bg-blue-400/15 text-blue-200 border-blue-300/25',
  medium: 'bg-amber-400/15 text-amber-200 border-amber-300/25',
  high: 'bg-orange-400/15 text-orange-200 border-orange-300/25',
  critical: 'bg-rose-400/15 text-rose-200 border-rose-300/25',
}

const DEFAULT_THRESHOLDS = [
  { service: 'ec2', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 85, severity: 'high' },
  { service: 'rds', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 80, severity: 'high' },
  { service: 'rds', metric_name: 'storage_used_percent', operator: 'gt', threshold_value: 90, severity: 'critical' },
  { service: 'rds', metric_name: 'database_connections', operator: 'gt', threshold_value: 100, severity: 'medium' },
  { service: 'lambda', metric_name: 'error_rate_percent', operator: 'gt', threshold_value: 5, severity: 'high' },
  { service: 'sqs', metric_name: 'messages_visible', operator: 'gt', threshold_value: 1000, severity: 'medium' },
  { service: 'sqs', metric_name: 'oldest_message_age_seconds', operator: 'gt', threshold_value: 3600, severity: 'high' },
  { service: 'elasticache', metric_name: 'cpu_utilization_percent', operator: 'gt', threshold_value: 75, severity: 'medium' },
  { service: 'elasticache', metric_name: 'cache_hit_ratio_percent', operator: 'lt', threshold_value: 80, severity: 'medium' },
]

export default function ThresholdsPage() {
  const [thresholds, setThresholds] = useState<Threshold[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newThreshold, setNewThreshold] = useState({
    service: 'ec2', metric_name: '', operator: 'gt', threshold_value: '', severity: 'medium',
  })

  useEffect(() => { fetchThresholds() }, [])

  const fetchThresholds = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getDefaultThresholds()
      setThresholds(data.thresholds || [])
    } catch {
      setThresholds(DEFAULT_THRESHOLDS.map((t) => ({
        PK: 'DEFAULT', SK: `${t.service}#${t.metric_name}`, enabled: true, ...t,
      })))
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async (threshold: Threshold) => {
    const key = threshold.SK
    setSaving(key)
    try {
      await adminApi.upsertThreshold('DEFAULT', threshold.service, threshold.metric_name, {
        operator: threshold.operator, threshold_value: threshold.threshold_value,
        severity: threshold.severity, enabled: !threshold.enabled,
      })
      setThresholds(ts => ts.map(t => t.SK === key ? { ...t, enabled: !t.enabled } : t))
    } catch {
      alert('Failed to update threshold')
    } finally {
      setSaving(null)
    }
  }

  const handleSave = async (threshold: Threshold) => {
    const key = threshold.SK
    setSaving(key)
    try {
      await adminApi.upsertThreshold('DEFAULT', threshold.service, threshold.metric_name, {
        operator: threshold.operator, threshold_value: threshold.threshold_value,
        severity: threshold.severity, enabled: threshold.enabled,
      })
    } catch {
      alert('Failed to save threshold')
    } finally {
      setSaving(null)
    }
  }

  const handleAddThreshold = async () => {
    if (!newThreshold.metric_name || !newThreshold.threshold_value) return
    setSaving('new')
    try {
      await adminApi.upsertThreshold('DEFAULT', newThreshold.service, newThreshold.metric_name, {
        operator: newThreshold.operator, threshold_value: parseFloat(newThreshold.threshold_value),
        severity: newThreshold.severity, enabled: true,
      })
      setShowAdd(false)
      setNewThreshold({ service: 'ec2', metric_name: '', operator: 'gt', threshold_value: '', severity: 'medium' })
      fetchThresholds()
    } catch {
      alert('Failed to add threshold')
    } finally {
      setSaving(null)
    }
  }

  const updateLocal = (sk: string, field: string, value: unknown) => {
    setThresholds(ts => ts.map(t => t.SK === sk ? { ...t, [field]: value } : t))
  }

  return (
    <AdminLayout>
      <div className="space-y-7">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-ink">Default thresholds</h1>
            <p className="mt-1 text-sm text-muted-ink">Applied to all customers unless overridden per-customer</p>
          </div>
          <div className="flex gap-3">
            <button onClick={fetchThresholds} className="btn-ghost"><RefreshCw className="h-4 w-4" /> Refresh</button>
            <button onClick={() => setShowAdd(true)} className="btn-primary"><Plus className="h-4 w-4" /> Add threshold</button>
          </div>
        </div>

        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-violet-400" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-left">
                    {['Service', 'Metric', 'Condition', 'Value', 'Severity', 'Enabled', 'Actions'].map(h => (
                      <th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {thresholds.map(t => (
                    <tr key={t.SK} className="border-b border-white/[0.06] transition-colors last:border-0 hover:bg-white/[0.04]">
                      <td className="px-5 py-4">
                        <span className="rounded-lg bg-white/10 px-2 py-0.5 font-mono text-xs text-cyan-200">{t.service}</span>
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-muted-ink">{t.metric_name}</td>
                      <td className="px-5 py-4">
                        <select value={t.operator} onChange={e => updateLocal(t.SK, 'operator', e.target.value)}
                          className="input-glass !w-auto !py-1 text-xs">
                          {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-4">
                        <input type="number" value={t.threshold_value}
                          onChange={e => updateLocal(t.SK, 'threshold_value', parseFloat(e.target.value))}
                          className="input-glass !w-24 !py-1 text-xs" />
                      </td>
                      <td className="px-5 py-4">
                        <select value={t.severity} onChange={e => updateLocal(t.SK, 'severity', e.target.value)}
                          className={`pill !py-1 capitalize ${SEVERITY_BADGE[t.severity] || ''}`}>
                          {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-4">
                        <button onClick={() => handleToggle(t)}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${t.enabled ? 'aurora-grad' : 'bg-white/15'}`}>
                          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${t.enabled ? 'translate-x-4' : 'translate-x-1'}`} />
                        </button>
                      </td>
                      <td className="px-5 py-4">
                        <button onClick={() => handleSave(t)} disabled={saving === t.SK}
                          className="inline-flex items-center gap-1 rounded-lg bg-white/10 px-2.5 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-white/20 disabled:opacity-50">
                          {saving === t.SK ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
          <div className="glass-card w-full max-w-md animate-fade-up">
            <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
              <h2 className="text-lg font-semibold text-ink">Add threshold</h2>
              <button onClick={() => setShowAdd(false)} className="text-faint-ink hover:text-ink">✕</button>
            </div>
            <div className="space-y-4 px-6 py-5">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-ink">Service</label>
                <select value={newThreshold.service} onChange={e => setNewThreshold(n => ({ ...n, service: e.target.value }))} className="input-glass">
                  {SERVICES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-ink">Metric name</label>
                <input value={newThreshold.metric_name} onChange={e => setNewThreshold(n => ({ ...n, metric_name: e.target.value }))}
                  className="input-glass" placeholder="cpu_utilization_percent" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted-ink">Operator</label>
                  <select value={newThreshold.operator} onChange={e => setNewThreshold(n => ({ ...n, operator: e.target.value }))} className="input-glass">
                    {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-muted-ink">Value</label>
                  <input type="number" value={newThreshold.threshold_value}
                    onChange={e => setNewThreshold(n => ({ ...n, threshold_value: e.target.value }))}
                    className="input-glass" placeholder="85" />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-ink">Severity</label>
                <select value={newThreshold.severity} onChange={e => setNewThreshold(n => ({ ...n, severity: e.target.value }))} className="input-glass">
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="flex gap-3 pt-1">
                <button onClick={() => setShowAdd(false)} className="btn-ghost flex-1">Cancel</button>
                <button onClick={handleAddThreshold} disabled={saving === 'new'} className="btn-primary flex-1">
                  {saving === 'new' ? 'Adding…' : 'Add threshold'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  )
}
