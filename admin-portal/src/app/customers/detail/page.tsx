'use client'

import { Suspense, useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import {
  ArrowLeft, Download, Key, Save, CheckCircle,
  XCircle, AlertTriangle, RefreshCw,
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

// Static export can't use a [id] dynamic segment — IDs are passed as ?id=…
// (useSearchParams needs a Suspense boundary in the App Router).
export default function CustomerDetailPage() {
  return (
    <Suspense fallback={null}>
      <CustomerDetailContent />
    </Suspense>
  )
}

function CustomerDetailContent() {
  const searchParams = useSearchParams()
  const id = searchParams.get('id') ?? ''
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', email: '', subscription_tier: '', aws_account_ids: '', status: '' })

  const fetchCustomer = useCallback(async () => {
    if (!id) { setLoading(false); return }
    setLoading(true)
    try {
      const data = await adminApi.getCustomer(id)
      const c = data.customer
      setCustomer(c)
      setForm({
        name: c.name || '', email: c.email || '',
        subscription_tier: c.subscription_tier || 'foundation',
        aws_account_ids: (c.aws_account_ids || []).join(', '),
        status: c.status || 'active',
      })
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetchCustomer() }, [fetchCustomer])

  const handleSave = async () => {
    setSaving(true)
    try {
      await adminApi.updateCustomer(id, {
        name: form.name, email: form.email, subscription_tier: form.subscription_tier,
        aws_account_ids: form.aws_account_ids.split(',').map(s => s.trim()).filter(Boolean),
        status: form.status,
      })
      await fetchCustomer()
    } catch {
      alert('Failed to save changes')
    } finally {
      setSaving(false)
    }
  }

  const handleRotateKey = async () => {
    if (!confirm('Rotate API key? The old key will stop working immediately.')) return
    try {
      const data = await adminApi.rotateApiKey(id)
      setNewApiKey(data.new_api_key)
    } catch {
      alert('Failed to rotate key')
    }
  }

  const handleDownloadCfn = async () => {
    try {
      const blob = await adminApi.downloadCfnTemplate(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tek-watch-agent-${id}.yaml`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Failed to download template')
    }
  }

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-violet-400" />
        </div>
      </AdminLayout>
    )
  }

  if (!customer) {
    return (
      <AdminLayout>
        <div className="py-16 text-center">
          <p className="text-muted-ink">Customer not found</p>
          <Link href="/customers" className="mt-2 inline-block text-sm text-violet-300 hover:underline">← Back to customers</Link>
        </div>
      </AdminLayout>
    )
  }

  const agentColor = {
    healthy: 'text-emerald-300', warning: 'text-amber-300',
    offline: 'text-rose-300', unknown: 'text-faint-ink',
  }[customer.agent_status] || 'text-faint-ink'

  return (
    <AdminLayout>
      <div className="max-w-3xl space-y-6">
        <div>
          <Link href="/customers" className="mb-4 flex items-center gap-1 text-sm text-muted-ink transition-colors hover:text-ink">
            <ArrowLeft className="h-4 w-4" /> Back to customers
          </Link>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-ink">{customer.name}</h1>
              <p className="mt-0.5 font-mono text-sm text-faint-ink">{customer.customer_id}</p>
            </div>
            <div className="flex gap-2">
              <button onClick={handleDownloadCfn} className="btn-ghost"><Download className="h-4 w-4" /> CloudFormation</button>
              <button onClick={handleRotateKey} className="btn-ghost !border-amber-300/30 !text-amber-200 hover:!bg-amber-400/10">
                <Key className="h-4 w-4" /> Rotate key
              </button>
            </div>
          </div>
        </div>

        {newApiKey && (
          <div className="glass-card border-amber-300/30 bg-amber-400/10 p-4">
            <p className="mb-1 font-semibold text-amber-200">New API key — save it now, it won&apos;t be shown again</p>
            <code className="block break-all rounded-lg border border-amber-300/20 bg-black/30 px-3 py-2 font-mono text-sm text-amber-100">{newApiKey}</code>
            <button onClick={() => setNewApiKey(null)} className="mt-2 text-xs text-amber-300 hover:underline">Dismiss</button>
          </div>
        )}

        <div className="glass-card p-5">
          <h2 className="mb-3 text-sm font-semibold text-muted-ink">Agent status</h2>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <div className={`flex items-center gap-2 font-medium capitalize ${agentColor}`}>
              {customer.agent_status === 'healthy' && <CheckCircle className="h-5 w-5" />}
              {customer.agent_status === 'warning' && <AlertTriangle className="h-5 w-5" />}
              {(customer.agent_status === 'offline' || customer.agent_status === 'unknown') && <XCircle className="h-5 w-5" />}
              {customer.agent_status || 'unknown'}
            </div>
            <div className="text-sm text-muted-ink">Last seen: <span className="font-medium text-ink">{formatRelativeTime(customer.last_agent_seen)}</span></div>
            <div className="text-sm text-muted-ink">Created: <span className="font-medium text-ink">{formatDate(customer.created_at)}</span></div>
          </div>
        </div>

        <div className="glass-card space-y-4 p-5">
          <h2 className="text-sm font-semibold text-muted-ink">Account details</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-muted-ink">Company name</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="input-glass" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-muted-ink">Contact email</label>
              <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} className="input-glass" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-muted-ink">Subscription tier</label>
              <select value={form.subscription_tier} onChange={e => setForm(f => ({ ...f, subscription_tier: e.target.value }))} className="input-glass">
                <option value="foundation">Foundation</option>
                <option value="growth">Growth</option>
                <option value="scale">Scale</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-muted-ink">Account status</label>
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className="input-glass">
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-muted-ink">
              AWS account IDs <span className="font-normal text-faint-ink">(comma-separated)</span>
            </label>
            <input value={form.aws_account_ids} onChange={e => setForm(f => ({ ...f, aws_account_ids: e.target.value }))}
              className="input-glass" placeholder="123456789012, 987654321098" />
          </div>
          <div className="flex justify-end">
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>
    </AdminLayout>
  )
}
