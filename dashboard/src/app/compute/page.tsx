'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Server, Zap, Layers } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_EC2, MOCK_LAMBDA, MOCK_ECS } from '@/lib/mockData'

function StateChip({ state }: { state: string }) {
  if (state === 'running') return <Badge variant="success">running</Badge>
  if (state === 'stopped') return <Badge variant="default">stopped</Badge>
  return <Badge variant="warning">{state}</Badge>
}

function CpuBar({ value }: { value: number }) {
  const col = value > 80 ? 'bg-red-500' : value > 60 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div className={`h-full ${col} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className={`text-xs font-medium w-10 text-right ${value > 80 ? 'text-red-400' : value > 60 ? 'text-amber-400' : 'text-slate-300'}`}>
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

export default function ComputePage() {
  const { loading: authLoading } = useAuth()
  const [tab, setTab] = useState<'ec2' | 'lambda' | 'ecs'>('ec2')

  const tabs = [
    { key: 'ec2',    label: 'EC2',    icon: Server, count: MOCK_EC2.length },
    { key: 'lambda', label: 'Lambda', icon: Zap,    count: MOCK_LAMBDA.length },
    { key: 'ecs',    label: 'ECS',    icon: Layers, count: MOCK_ECS.length },
  ] as const

  const running = MOCK_EC2.filter(i => i.state === 'running').length

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
          <h1 className="text-2xl font-bold text-white">Compute</h1>
          <p className="text-slate-400 text-sm mt-0.5">EC2 · Lambda · ECS — {running} instances running</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-white/[0.03] border border-white/[0.06] rounded-xl w-fit">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.key
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}>
              <t.icon className="w-4 h-4" />
              {t.label}
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.key ? 'bg-white/20' : 'bg-white/[0.06]'}`}>
                {t.count}
              </span>
            </button>
          ))}
        </div>

        {/* EC2 */}
        {tab === 'ec2' && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Name', 'Type', 'State', 'Region / AZ', 'CPU', 'Net In', 'Private IP'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_EC2.map((i, idx) => (
                      <tr key={i.instance_id} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3">
                          <div className="font-medium text-white">{i.instance_name}</div>
                          <div className="text-xs text-slate-500 font-mono">{i.instance_id.slice(0, 19)}</div>
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-400">{i.instance_type}</td>
                        <td className="px-4 py-3"><StateChip state={i.state} /></td>
                        <td className="px-4 py-3">
                          <div className="text-xs text-slate-300">{i.region}</div>
                          <div className="text-xs text-slate-500">{i.az}</div>
                        </td>
                        <td className="px-4 py-3 w-36">
                          {i.state === 'running' ? <CpuBar value={i.cpu} /> : <span className="text-xs text-slate-600">—</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-300">{i.net_in > 0 ? `${i.net_in} Mbps` : '—'}</td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-400">{i.private_ip}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Lambda */}
        {tab === 'lambda' && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Function', 'Runtime', 'Memory', 'Invocations/h', 'Errors/h', 'Avg Duration', 'Throttles'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_LAMBDA.map((fn, idx) => {
                      const errPct = fn.invocations_1h > 0 ? ((fn.errors_1h / fn.invocations_1h) * 100).toFixed(1) : '0.0'
                      return (
                        <tr key={fn.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                          <td className="px-4 py-3 font-medium text-white">{fn.name}</td>
                          <td className="px-4 py-3 text-xs font-mono text-slate-400">{fn.runtime}</td>
                          <td className="px-4 py-3 text-xs text-slate-300">{fn.memory_mb} MB</td>
                          <td className="px-4 py-3 text-slate-300">{fn.invocations_1h.toLocaleString()}</td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-medium ${fn.errors_1h > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                              {fn.errors_1h}{fn.errors_1h > 0 && <span className="text-slate-500"> ({errPct}%)</span>}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs">
                            <span className={fn.duration_avg_ms > 2000 ? 'text-amber-400' : 'text-slate-300'}>
                              {fn.duration_avg_ms.toLocaleString()} ms
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {fn.throttles_1h > 0
                              ? <Badge variant="warning">{fn.throttles_1h}</Badge>
                              : <span className="text-xs text-emerald-400">0</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* ECS */}
        {tab === 'ecs' && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Cluster', 'Service', 'Tasks', 'CPU', 'Memory'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_ECS.map((svc, idx) => (
                      <tr key={`${svc.cluster}-${svc.service}`} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 text-xs font-mono text-slate-400">{svc.cluster}</td>
                        <td className="px-4 py-3 font-medium text-white">{svc.service}</td>
                        <td className="px-4 py-3">
                          <span className={svc.running < svc.desired ? 'text-red-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                            {svc.running}
                          </span>
                          <span className="text-slate-500 text-xs">/{svc.desired}</span>
                        </td>
                        <td className="px-4 py-3 w-36"><CpuBar value={svc.cpu_pct} /></td>
                        <td className="px-4 py-3 w-36"><CpuBar value={svc.mem_pct} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  )
}
