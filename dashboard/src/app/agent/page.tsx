'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Activity, CheckCircle, Radio, Clock } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_AGENT, MOCK_CUSTOMER } from '@/lib/mockData'
import { formatRelativeTime } from '@/lib/utils'

export default function AgentPage() {
  const { loading: authLoading } = useAuth()
  const a = MOCK_AGENT

  if (authLoading) return (
    <DashboardLayout>
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" />
      </div>
    </DashboardLayout>
  )

  return (
    <DashboardLayout>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Agent</h1>
          <p className="text-slate-400 text-sm mt-0.5">Collection agent running in the customer&apos;s AWS account</p>
        </div>

        {/* Status hero */}
        <Card className={a.status === 'healthy' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${a.status === 'healthy' ? 'bg-emerald-500/20 border border-emerald-500/30' : 'bg-amber-500/20 border border-amber-500/30'}`}>
                <Radio className={`w-7 h-7 ${a.status === 'healthy' ? 'text-emerald-400' : 'text-amber-400'}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xl font-bold text-white capitalize">{a.status}</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <p className="text-sm text-slate-400">
                  Customer <span className="text-white font-mono">{a.customer_id}</span> · Version {a.version}
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="text-slate-500 text-xs mb-0.5">Last heartbeat</p>
                <p className="font-medium text-white">{formatRelativeTime(a.last_heartbeat)}</p>
                <p className="text-xs text-slate-500 mt-1">{a.collection_interval_s}s interval</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Metrics Collected', value: a.metrics_collected_total.toLocaleString(), icon: Activity, color: 'text-indigo-400' },
            { label: 'Regions Covered',   value: a.regions.length.toString(),               icon: Radio,    color: 'text-blue-400' },
            { label: 'Active Collectors', value: a.collectors.filter(c => c.status === 'ok').length.toString(), icon: CheckCircle, color: 'text-emerald-400' },
            { label: 'Collection Interval', value: `${a.collection_interval_s}s`,           icon: Clock,    color: 'text-amber-400' },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <s.icon className={`w-4 h-4 ${s.color}`} />
                  <span className="text-xs text-slate-500">{s.label}</span>
                </div>
                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Regions */}
        <Card>
          <CardContent className="p-5">
            <h3 className="font-semibold text-white mb-3">Regions Monitored</h3>
            <div className="flex flex-wrap gap-2">
              {MOCK_CUSTOMER.regions.map(r => (
                <div key={r} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span className="text-sm font-mono text-slate-300">{r}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Collectors table */}
        <Card>
          <CardContent className="p-0">
            <div className="px-5 pt-5 pb-3">
              <h3 className="font-semibold text-white">Collectors</h3>
              <p className="text-xs text-slate-500 mt-0.5">{a.collectors.length} collectors · all healthy</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    {['Collector', 'Status', 'Last Run', 'Resources', 'Metrics Sent'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {a.collectors.map((c, idx) => (
                    <tr key={c.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                      <td className="px-4 py-3 font-medium text-white">{c.name}</td>
                      <td className="px-4 py-3">
                        {c.status === 'ok'
                          ? <Badge variant="success">ok</Badge>
                          : <Badge variant="error">{c.status}</Badge>}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{formatRelativeTime(c.last_run)}</td>
                      <td className="px-4 py-3 text-slate-300">{c.resources}</td>
                      <td className="px-4 py-3 text-slate-300">{c.metrics_sent}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
