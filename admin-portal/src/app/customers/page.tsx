'use client'

import { useEffect, useState } from 'react'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import {
  Users, Plus, RefreshCw, Download, Key, Search,
  CheckCircle, XCircle, AlertTriangle, ChevronRight, Activity, ShieldCheck,
} from 'lucide-react'
import Link from 'next/link'

interface Customer {
  customer_id: string
  name: string
  email: string
  subscription_tier: string
  aws_account_ids: string[]
  status: string
  agent_status: string
  last_agent_seen: string | null
  created_at: string
}

const TIER_BADGE: Record<string, string> = {
  foundation: 'bg-slate-400/15 text-slate-200 border-slate-300/20',
  growth: 'bg-blue-400/15 text-blue-200 border-blue-300/25',
  scale: 'bg-violet-400/15 text-violet-200 border-violet-300/25',
  enterprise: 'bg-amber-400/15 text-amber-200 border-amber-300/25',
}

const AGENT_PILL: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
  healthy: { cls: 'text-emerald-300', icon: <CheckCircle className="h-3.5 w-3.5" />, label: 'healthy' },
  warning: { cls: 'text-amber-300', icon: <AlertTriangle className="h-3.5 w-3.5" />, label: 'warning' },
  offline: { cls: 'text-rose-300', icon: <XCircle className="h-3.5 w-3.5" />, label: 'offline' },
  unknown: { cls: 'text-faint-ink', icon: <XCircle className="h-3.5 w-3.5" />, label: 'unknown' },
}

function Kpi({ label, value, sub, icon, accent }: {
  label: string; value: string | number; sub?: string; icon: React.ReactNode; accent: string
}) {
  return (
    <div className="kpi">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-faint-ink">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-ink">{value}</p>
          {sub && <p className="mt-1 text-xs text-muted-ink">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${accent}`}>{icon}</div>
      </div>
    </div>
  )
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newApiKey, setNewApiKey] = useState<{ customerId: string; key: string } | null>(null)

  useEffect(() => { fetchCustomers() }, [])

  const fetchCustomers = async () => {
    setLoading(true)
    try {
      const data = await adminApi.listCustomers()
      setCustomers(data.customers || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleRotateKey = async (customerId: string) => {
    if (!confirm(`Rotate API key for ${customerId}? The old key will stop working immediately.`)) return
    try {
      const data = await adminApi.rotateApiKey(customerId)
      setNewApiKey({ customerId, key: data.new_api_key })
    } catch {
      alert('Failed to rotate key')
    }
  }

  const handleDownloadCfn = async (customerId: string) => {
    try {
      const blob = await adminApi.downloadCfnTemplate(customerId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tek-watch-agent-${customerId}.yaml`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Failed to download template')
    }
  }

  const filtered = customers.filter(c =>
    c.customer_id.toLowerCase().includes(search.toLowerCase()) ||
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  )

  const activeCount = customers.filter(c => c.status === 'active').length
  const healthyCount = customers.filter(c => c.agent_status === 'healthy').length
  const offlineCount = customers.filter(c => c.agent_status === 'offline').length

  return (
    <AdminLayout>
      <div className="space-y-7">
        {/* Header */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-ink">Customers</h1>
            <p className="mt-1 text-sm text-muted-ink">Manage tenant accounts, agents and API keys</p>
          </div>
          <div className="flex gap-3">
            <button onClick={fetchCustomers} className="btn-ghost">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button onClick={() => setShowCreate(true)} className="btn-primary">
              <Plus className="h-4 w-4" /> New customer
            </button>
          </div>
        </div>

        {/* KPI tiles */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Kpi label="Total customers" value={customers.length} sub="across all tiers"
            icon={<Users className="h-5 w-5 text-cyan-300" />} accent="bg-cyan-400/15" />
          <Kpi label="Active" value={activeCount} sub={`${customers.length - activeCount} suspended`}
            icon={<ShieldCheck className="h-5 w-5 text-violet-300" />} accent="bg-violet-400/15" />
          <Kpi label="Agents healthy" value={healthyCount} sub="reporting < 20 min"
            icon={<Activity className="h-5 w-5 text-emerald-300" />} accent="bg-emerald-400/15" />
          <Kpi label="Agents offline" value={offlineCount} sub="needs attention"
            icon={<XCircle className="h-5 w-5 text-rose-300" />} accent="bg-rose-400/15" />
        </div>

        {/* New API key banner */}
        {newApiKey && (
          <div className="glass-card border-amber-300/30 bg-amber-400/10 p-4">
            <p className="mb-1 font-semibold text-amber-200">
              New API key for {newApiKey.customerId} — save it now, it won&apos;t be shown again
            </p>
            <code className="block break-all rounded-lg border border-amber-300/20 bg-black/30 px-3 py-2 font-mono text-sm text-amber-100">
              {newApiKey.key}
            </code>
            <button onClick={() => setNewApiKey(null)} className="mt-2 text-xs text-amber-300 hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-faint-ink" />
          <input
            type="text"
            placeholder="Search by ID, name, or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-glass pl-10"
          />
        </div>

        {/* Table */}
        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="flex h-48 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-violet-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center text-faint-ink">
              <Users className="mb-3 h-10 w-10" />
              <p className="text-sm">No customers found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10 text-left">
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Customer</th>
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Tier</th>
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Agent</th>
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Last seen</th>
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Status</th>
                    <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-faint-ink">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(c => {
                    const agent = AGENT_PILL[c.agent_status] || AGENT_PILL.unknown
                    return (
                      <tr key={c.customer_id} className="border-b border-white/[0.06] transition-colors last:border-0 hover:bg-white/[0.04]">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-ink">{c.name}</div>
                          <div className="font-mono text-xs text-faint-ink">{c.customer_id}</div>
                          <div className="text-xs text-faint-ink">{c.email}</div>
                        </td>
                        <td className="px-5 py-4">
                          <span className={`pill capitalize ${TIER_BADGE[c.subscription_tier] || TIER_BADGE.foundation}`}>
                            {c.subscription_tier}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex items-center gap-1.5 text-xs font-medium capitalize ${agent.cls}`}>
                            {agent.icon} {agent.label}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-xs text-muted-ink">{formatRelativeTime(c.last_agent_seen)}</td>
                        <td className="px-5 py-4">
                          <span className={`pill ${c.status === 'active' ? 'bg-emerald-400/15 text-emerald-300 border-emerald-300/25' : 'bg-rose-400/15 text-rose-300 border-rose-300/25'}`}>
                            {c.status}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-1">
                            <Link href={`/customers/detail?id=${c.customer_id}`}
                              className="rounded-lg p-1.5 text-faint-ink transition-colors hover:bg-violet-400/15 hover:text-violet-200" title="View details">
                              <ChevronRight className="h-4 w-4" />
                            </Link>
                            <button onClick={() => handleDownloadCfn(c.customer_id)}
                              className="rounded-lg p-1.5 text-faint-ink transition-colors hover:bg-emerald-400/15 hover:text-emerald-200" title="Download CloudFormation template">
                              <Download className="h-4 w-4" />
                            </button>
                            <button onClick={() => handleRotateKey(c.customer_id)}
                              className="rounded-lg p-1.5 text-faint-ink transition-colors hover:bg-amber-400/15 hover:text-amber-200" title="Rotate API key">
                              <Key className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateCustomerModal
          onClose={() => setShowCreate(false)}
          onCreated={(result) => {
            setShowCreate(false)
            setNewApiKey({ customerId: result.customer_id, key: result.api_key })
            fetchCustomers()
          }}
        />
      )}
    </AdminLayout>
  )
}

function CreateCustomerModal({
  onClose, onCreated,
}: {
  onClose: () => void
  onCreated: (result: { customer_id: string; api_key: string }) => void
}) {
  const [form, setForm] = useState({ name: '', email: '', subscription_tier: 'foundation', aws_account_ids: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const accountIds = form.aws_account_ids.split(',').map(s => s.trim()).filter(Boolean)
      const result = await adminApi.createCustomer({
        name: form.name, email: form.email,
        subscription_tier: form.subscription_tier, aws_account_ids: accountIds,
      })
      onCreated({ customer_id: result.customer_id, api_key: result.api_key })
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create customer')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="glass-card w-full max-w-md animate-fade-up">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="text-lg font-semibold text-ink">New customer</h2>
          <button onClick={onClose} className="text-faint-ink hover:text-ink"><XCircle className="h-5 w-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          <div>
            <label className="mb-1 block text-sm font-medium text-muted-ink">Company name</label>
            <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="input-glass" placeholder="Acme Corp" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted-ink">Contact email</label>
            <input required type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              className="input-glass" placeholder="admin@acme.com" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted-ink">Subscription tier</label>
            <select value={form.subscription_tier} onChange={e => setForm(f => ({ ...f, subscription_tier: e.target.value }))}
              className="input-glass">
              <option value="foundation">Foundation</option>
              <option value="growth">Growth</option>
              <option value="scale">Scale</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted-ink">
              AWS account IDs <span className="font-normal text-faint-ink">(comma-separated)</span>
            </label>
            <input value={form.aws_account_ids} onChange={e => setForm(f => ({ ...f, aws_account_ids: e.target.value }))}
              className="input-glass" placeholder="123456789012, 987654321098" />
          </div>
          {error && (
            <p className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{error}</p>
          )}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading ? 'Creating…' : 'Create customer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
