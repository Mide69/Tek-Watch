'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Sparkline } from '@/components/ui/MiniChart'
import { Server, Zap, Layers } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useEC2, useLambda, useECS } from '@/hooks/useData'

function StateChip({ state }: { state: string }) {
  if (state === 'running') return <Badge variant="success">running</Badge>
  if (state === 'stopped') return <Badge variant="default">stopped</Badge>
  return <Badge variant="warning">{state}</Badge>
}

function PctBar({ value }: { value: number }) {
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
  const { customerId }  = useAuth()
  const { timeRange }   = useDashboard()
  const [tab, setTab]   = useState<'ec2' | 'lambda' | 'ecs'>('ec2')

  const { data: ec2,    isLoading: ec2Loading }    = useEC2()
  const { data: lambda, isLoading: lambdaLoading } = useLambda()
  const { data: ecs,    isLoading: ecsLoading }    = useECS()

  const isLoading = (tab === 'ec2' && ec2Loading)
    || (tab === 'lambda' && lambdaLoading)
    || (tab === 'ecs' && ecsLoading)

  const running = (ec2 || []).filter(i => i.state === 'running').length

  const tabs = [
    { key: 'ec2',    label: 'EC2',    icon: Server, count: (ec2 || []).length },
    { key: 'lambda', label: 'Lambda', icon: Zap,    count: (lambda || []).length },
    { key: 'ecs',    label: 'ECS',    icon: Layers, count: (ecs || []).length },
  ] as const

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Compute</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            EC2 · Lambda · ECS — {running} instances running · {TIME_RANGE_LABELS[timeRange]}
          </p>
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

        {isLoading ? (
          <Card><CardContent className="p-6"><TableSkeleton rows={8} cols={6} /></CardContent></Card>
        ) : (
          <>
            {/* EC2 */}
            {tab === 'ec2' && (
              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/[0.06]">
                          {['Name', 'Type', 'State', 'Region / AZ', 'CPU', 'CPU Trend', 'Net In', 'Private IP'].map(h => (
                            <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(ec2 || []).map((i, idx) => (
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
                            <td className="px-4 py-3 w-32">
                              {i.state === 'running' ? <PctBar value={i.cpu} /> : <span className="text-xs text-slate-600">—</span>}
                            </td>
                            <td className="px-4 py-3 w-28">
                              {i.state === 'running' && i.metrics?.cpu ? (
                                <Sparkline
                                  data={i.metrics.cpu.map((p: { value: number }) => ({ value: p.value }))}
                                  color={i.cpu > 80 ? '#f87171' : i.cpu > 60 ? '#fbbf24' : '#6366f1'}
                                  height={28}
                                />
                              ) : <span className="text-xs text-slate-600">—</span>}
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-300">
                              {i.network_in > 0 ? `${i.network_in} Mbps` : '—'}
                            </td>
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
                          {['Function', 'Runtime', 'Memory', 'Invocations', 'Errors', 'Avg Duration', 'Throttles', 'Trend'].map(h => (
                            <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(lambda || []).map((fn, idx) => {
                          const errPct = fn.invocations > 0 ? ((fn.errors / fn.invocations) * 100).toFixed(1) : '0.0'
                          const durationS = fn.duration_avg >= 1000 ? `${(fn.duration_avg / 1000).toFixed(1)}s` : `${fn.duration_avg} ms`
                          return (
                            <tr key={fn.function_name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                              <td className="px-4 py-3 font-medium text-white max-w-[180px] truncate">{fn.function_name}</td>
                              <td className="px-4 py-3 text-xs font-mono text-slate-400">{fn.runtime}</td>
                              <td className="px-4 py-3 text-xs text-slate-300">{fn.memory} MB</td>
                              <td className="px-4 py-3 text-slate-300">{fn.invocations.toLocaleString()}</td>
                              <td className="px-4 py-3">
                                <span className={`text-xs font-medium ${fn.errors > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                                  {fn.errors}{fn.errors > 0 && <span className="text-slate-500"> ({errPct}%)</span>}
                                </span>
                              </td>
                              <td className="px-4 py-3 text-xs">
                                <span className={fn.duration_avg > 2000 ? 'text-amber-400' : 'text-slate-300'}>
                                  {durationS}
                                </span>
                              </td>
                              <td className="px-4 py-3">
                                {fn.throttles > 0
                                  ? <Badge variant="warning">{fn.throttles}</Badge>
                                  : <span className="text-xs text-emerald-400">0</span>}
                              </td>
                              <td className="px-4 py-3 w-28">
                                {fn.metrics?.invocations ? (
                                  <Sparkline
                                    data={fn.metrics.invocations.map((p: { value: number }) => ({ value: p.value }))}
                                    color={fn.function_name === 'acme-image-processor' ? '#f97316' : '#6366f1'}
                                    height={28}
                                  />
                                ) : null}
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
                          {['Cluster', 'Service', 'Tasks', 'Status', 'CPU', 'Memory'].map(h => (
                            <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(ecs || []).map((svc, idx) => (
                          <tr key={`${svc.cluster}-${svc.service_name}`} className={`border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                            <td className="px-4 py-3 text-xs font-mono text-slate-400">{svc.cluster}</td>
                            <td className="px-4 py-3 font-medium text-white">{svc.service_name}</td>
                            <td className="px-4 py-3">
                              <span className={svc.running < svc.desired ? 'text-red-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                                {svc.running}
                              </span>
                              <span className="text-slate-500 text-xs">/{svc.desired}</span>
                              {svc.pending > 0 && <span className="text-amber-400 text-xs ml-1">(+{svc.pending} pending)</span>}
                            </td>
                            <td className="px-4 py-3"><Badge variant="success">{svc.status}</Badge></td>
                            <td className="px-4 py-3 w-36"><PctBar value={svc.cpu} /></td>
                            <td className="px-4 py-3 w-36"><PctBar value={svc.memory} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
