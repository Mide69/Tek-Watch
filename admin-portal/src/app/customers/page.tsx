'use client'

import { useEffect, useState } from 'react'
import AdminLayout from '@/components/AdminLayout'
import adminApi from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import {
  Users, Plus, RefreshCw, Download, Key, Search,
  CheckCircle, XCircle, AlertTriangle, ChevronRight,
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

const TIER_COLORS: Record<string, string> = {
  foundation: 'bg-gray-100 text-gray-700',
  growth:     'bg-blue-100 text-blue-700',
  scale:      'bg-purple-100 text-purple-700',
  enterprise: 'bg-amber-100 text-amber-700',
}

const AGENT_ICON: Record<string, React.ReactNode> = {
  healthy: <CheckCircle className="h-4 w-4 text-green-500" />,
  warning: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
  offline: <XCircle className="h-4 w-4 text-red-500" />,
  unknown: <XCircle className="h-4 w-4 text-gray-400" />,
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
    } catch (e) {
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
    } catch (e) {
      alert('Failed to download template')
    }
  }

  const filtered = customers.filter(c =>
    c.customer_id.toLowerCase().includes(search.toLowerCase()) ||
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.email.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
            <p className="text-sm text-gray-500 mt-1">
              {customers.length} total · {customers.filter(c => c.status === 'active').length} active
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={fetchCustomers}
              className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Plus className="h-4 w-4" />
              New Customer
            </button>
          </div>
        </div>

        {/* New API key banner */}
        {newApiKey && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <p className="font-semibold text-amber-900 mb-1">
              New API key for {newApiKey.customerId} — save it now, it won&apos;t be shown again
            </p>
            <code className="block bg-white border border-amber-200 rounded px-3 py-2 text-sm font-mono break-all">
              {newApiKey.key}
            </code>
            <button
              onClick={() => setNewApiKey(null)}
              className="mt-2 text-xs text-amber-700 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by ID, name, or email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-48">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400">
              <Users className="h-10 w-10 mb-3" />
              <p className="text-sm">No customers found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Customer</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Tier</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Agent</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Last Seen</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filtered.map(c => (
                    <tr key={c.customer_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{c.name}</div>
                        <div className="text-xs text-gray-500 font-mono">{c.customer_id}</div>
                        <div className="text-xs text-gray-400">{c.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${TIER_COLORS[c.subscription_tier] || 'bg-gray-100 text-gray-700'}`}>
                          {c.subscription_tier}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          {AGENT_ICON[c.agent_status] || AGENT_ICON.unknown}
                          <span className="capitalize text-xs">{c.agent_status || 'unknown'}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {formatRelativeTime(c.last_agent_seen)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          c.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/customers/detail?id=${c.customer_id}`}
                            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                            title="View details"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Link>
                          <button
                            onClick={() => handleDownloadCfn(c.customer_id)}
                            className="p-1.5 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded"
                            title="Download CloudFormation template"
                          >
                            <Download className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleRotateKey(c.customer_id)}
                            className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded"
                            title="Rotate API key"
                          >
                            <Key className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Create Customer Modal */}
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
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (result: { customer_id: string; api_key: string }) => void
}) {
  const [form, setForm] = useState({
    name: '',
    email: '',
    subscription_tier: 'foundation',
    aws_account_ids: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const accountIds = form.aws_account_ids
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)

      const result = await adminApi.createCustomer({
        name: form.name,
        email: form.email,
        subscription_tier: form.subscription_tier,
        aws_account_ids: accountIds,
      })
      onCreated({ customer_id: result.customer_id, api_key: result.api_key })
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create customer')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">New Customer</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XCircle className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
            <input
              required
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Acme Corp"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contact Email</label>
            <input
              required
              type="email"
              value={form.email}
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              className="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="admin@acme.com"
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
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Creating…' : 'Create Customer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
