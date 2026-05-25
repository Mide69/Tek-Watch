'use client'

import { useEffect, useState } from 'react'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { Settings, Save, RefreshCw, Plus, Trash2 } from 'lucide-react'

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
  { value: 'gt',  label: '> Greater than' },
  { value: 'gte', label: '≥ Greater than or equal' },
  { value: 'lt',  label: '< Less than' },
  { value: 'lte', label: '≤ Less than or equal' },
]
const SEVERITIES = ['low', 'medium', 'high', 'critical']

const SEVERITY_COLORS: Record<string, string> = {
  low:      'bg-blue-100 text-blue-700',
  medium:   'bg-yellow-100 text-yellow-700',
  high:     'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
}

const DEFAULT_THRESHOLDS = [
  { service: 'ec2',          metric_name: 'cpu_utilization_percent',  operator: 'gt',  threshold_value: 85,   severity: 'high' },
  { service: 'rds',          metric_name: 'cpu_utilization_percent',  operator: 'gt',  threshold_value: 80,   severity: 'high' },
  { service: 'rds',          metric_name: 'storage_used_percent',     operator: 'gt',  threshold_value: 90,   severity: 'critical' },
  { service: 'rds',          metric_name: 'database_connections',     operator: 'gt',  threshold_value: 100,  severity: 'medium' },
  { service: 'lambda',       metric_name: 'error_rate_percent',       operator: 'gt',  threshold_value: 5,    severity: 'high' },
  { service: 'sqs',          metric_name: 'messages_visible',         operator: 'gt',  threshold_value: 1000, severity: 'medium' },
  { service: 'sqs',          metric_name: 'oldest_message_age_seconds', operator: 'gt', threshold_value: 3600, severity: 'high' },
  { service: 'elasticache',  metric_name: 'cpu_utilization_percent',  operator: 'gt',  threshold_value: 75,   severity: 'medium' },
  { service: 'elasticache',  metric_name: 'cache_hit_ratio_percent',  operator: 'lt',  threshold_value: 80,   severity: 'medium' },
]

export default function ThresholdsPage() {
  const [thresholds, setThresholds] = useState<Threshold[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newThreshold, setNewThreshold] = useState({
    service: 'ec2',
    metric_name: '',
    operator: 'gt',
    threshold_value: '',
    severity: 'medium',
  })

  useEffect(() => { fetchThresholds() }, [])

  const fetchThresholds = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getDefaultThresholds()
      setThresholds(data.thresholds || [])
    } catch {
      // If API not available, show defaults
      setThresholds(DEFAULT_THRESHOLDS.map((t, i) => ({
        PK: 'DEFAULT',
        SK: `${t.service}#${t.metric_name}`,
        enabled: true,
        ...t,
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
        operator: threshold.operator,
        threshold_value: threshold.threshold_value,
        severity: threshold.severity,
        enabled: !threshold.enabled,
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
        operator: threshold.operator,
        threshold_value: threshold.threshold_value,
        severity: threshold.severity,
        enabled: threshold.enabled,
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
        operator: newThreshold.operator,
        threshold_value: parseFloat(newThreshold.threshold_value),
        severity: newThreshold.severity,
        enabled: true,
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
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Default Thresholds</h1>
            <p className="text-sm text-gray-500 mt-1">
              These apply to all customers unless overridden per-customer
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={fetchThresholds}
              className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              Add Threshold
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Service</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Metric</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Condition</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Value</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Severity</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Enabled</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {thresholds.map(t => (
                    <tr key={t.SK} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="inline-flex px-2 py-0.5 rounded text-xs font-mono bg-gray-100 text-gray-700">
                          {t.service}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">{t.metric_name}</td>
                      <td className="px-4 py-3">
                        <select
                          value={t.operator}
                          onChange={e => updateLocal(t.SK, 'operator', e.target.value)}
                          className="px-2 py-1 border rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          {OPERATORS.map(op => (
                            <option key={op.value} value={op.value}>{op.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={t.threshold_value}
                          onChange={e => updateLocal(t.SK, 'threshold_value', parseFloat(e.target.value))}
                          className="w-24 px-2 py-1 border rounded text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={t.severity}
                          onChange={e => updateLocal(t.SK, 'severity', e.target.value)}
                          className={`px-2 py-1 rounded text-xs font-medium border-0 focus:outline-none focus:ring-1 focus:ring-blue-500 ${SEVERITY_COLORS[t.severity] || ''}`}
                        >
                          {SEVERITIES.map(s => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleToggle(t)}
                          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                            t.enabled ? 'bg-blue-600' : 'bg-gray-200'
                          }`}
                        >
                          <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                            t.enabled ? 'translate-x-4' : 'translate-x-1'
                          }`} />
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleSave(t)}
                          disabled={saving === t.SK}
                          className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                        >
                          {saving === t.SK
                            ? <RefreshCw className="h-3 w-3 animate-spin" />
                            : <Save className="h-3 w-3" />}
                          Save
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

      {/* Add Threshold Modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="text-lg font-semibold">Add Threshold</h2>
              <button onClick={() => setShowAdd(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Service</label>
                <select
                  value={newThreshold.service}
                  onChange={e => setNewThreshold(n => ({ ...n, service: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {SERVICES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Metric Name</label>
                <input
                  value={newThreshold.metric_name}
                  onChange={e => setNewThreshold(n => ({ ...n, metric_name: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="cpu_utilization_percent"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Operator</label>
                  <select
                    value={newThreshold.operator}
                    onChange={e => setNewThreshold(n => ({ ...n, operator: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {OPERATORS.map(op => <option key={op.value} value={op.value}>{op.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
                  <input
                    type="number"
                    value={newThreshold.threshold_value}
                    onChange={e => setNewThreshold(n => ({ ...n, threshold_value: e.target.value }))}
                    className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="85"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                <select
                  value={newThreshold.severity}
                  onChange={e => setNewThreshold(n => ({ ...n, severity: e.target.value }))}
                  className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowAdd(false)}
                  className="flex-1 px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddThreshold}
                  disabled={saving === 'new'}
                  className="flex-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving === 'new' ? 'Adding…' : 'Add Threshold'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </AdminLayout>
  )
}
