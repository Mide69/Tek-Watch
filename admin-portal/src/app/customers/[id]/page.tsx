'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
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

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    email: '',
    subscription_tier: '',
    aws_account_ids: '',
    status: '',
  })

  useEffect(() => {
    fetchCustomer()
  }, [id])

  const fetchCustomer = async () => {
    setLoading(true)
    try {
      const data = await adminApi.getCustomer(id)
      const c = data.customer
      setCustomer(c)
      setForm({
        name: c.name || '',
        email: c.email || '',
        subscription_tier: c.subscription_tier || 'foundation',
        aws_account_ids: (c.aws_account_ids || []).join(', '),
        status: c.status || 'active',
      })
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await adminApi.updateCustomer(id, {
        name: form.name,
        email: form.email,
        subscription_tier: form.subscription_tier,
        aws_account_ids: form.aws_account_ids.split(',').map(s => s.trim()).filter(Boolean),
        status: form.status,
      })
      await fetchCustomer()
    } catch (e) {
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
    } catch (e) {
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
    } catch (e) {
      alert('Failed to download template')
    }
  }

  if (loading) {
    return (
      <AdminLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      </AdminLayout>
    )
  }

  if (!customer) {
    return (
      <AdminLayout>
        <div className="text-center py-16">
          <p className="text-gray-500">Customer not found</p>
          <Link href="/customers" className="text-blue-600 hover:underline text-sm mt-2 inline-block">
            ← Back to customers
          </Link>
        </div>
      </AdminLayout>
    )
  }

  const agentStatusColor = {
    healthy: 'text-green-600',
    warning: 'text-yellow-600',
    offline: 'text-red-600',
    unknown: 'text-gray-400',
  }[customer.agent_status] || 'text-gray-400'

  return (
    <AdminLayout>
      <div className="space-y-6 max-w-3xl">
        {/* Back + header */}
        <div>
          <Link
            href="/customers"
            className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
          >
            <ArrowLeft className="h-4 w-4" /> Back to customers
          </Link>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{customer.name}</h1>
              <p className="text-sm font-mono text-gray-500 mt-0.5">{customer.customer_id}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDownloadCfn}
                className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
              >
                <Download className="h-4 w-4" />
                CloudFormation
              </button>
              <button
                onClick={handleRotateKey}
                className="flex items-center gap-2 px-3 py-2 text-sm border border-amber-300 text-amber-700 rounded-lg hover:bg-amber-50"
              >
                <Key className="h-4 w-4" />
                Rotate Key
              </button>
            </div>
          </div>
        </div>

        {/* New API key banner */}
        {newApiKey && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p className="font-semibold text-amber-900 mb-1">
              New API key — save it now, it won't be shown again
            </p>
            <code className="block bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono break-all">
              {newApiKey}
            </code>
            <button onClick={() => setNewApiKey(null)} className="mt-2 text-xs text-amber-700 hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Agent status card */}
        <div className="bg-white rounded-lg border p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Agent Status</h2>
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 font-medium capitalize ${agentStatusColor}`}>
              {customer.agent_status === 'healthy' && <CheckCircle className="h-5 w-5" />}
              {customer.agent_status === 'warning' && <AlertTriangle className="h-5 w-5" />}
              {(customer.agent_status === 'offline' || customer.agent_status === 'unknown') && (
                <XCircle className="h-5 w-5" />
              )}
              {customer.agent_status || 'unknown'}
            </div>
            <div className="text-sm text-gray-500">
              Last seen: <span className="font-medium">{formatRelativeTime(customer.last_agent_seen)}</span>
            </div>
            <div className="text-sm text-gray-500">
              Created: <span className="font-medium">{formatDate(customer.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Edit form */}
        <div className="bg-white rounded-lg border p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">Account Details</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contact Email</label>
              <input
                type="email"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subscription Tier</label>
              <select
                value={form.subscription_tier}
                onChange={e => setForm(f => ({ ...f, subscription_tier: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="foundation">Foundation</option>
                <option value="growth">Growth</option>
                <option value="scale">Scale</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Account Status</label>
              <select
                value={form.status}
                onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              AWS Account IDs <span className="text-gray-400 font-normal">(comma-separated)</span>
            </label>
            <input
              value={form.aws_account_ids}
              onChange={e => setForm(f => ({ ...f, aws_account_ids: e.target.value }))}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="123456789012, 987654321098"
            />
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </AdminLayout>
  )
}
