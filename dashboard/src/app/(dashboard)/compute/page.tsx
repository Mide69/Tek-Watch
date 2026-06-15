'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Sparkline } from '@/components/ui/MiniChart'
import { Server, Zap, Layers, ServerOff } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useEC2, useLambda, useECS } from '@/hooks/useData'
import { cn } from '@/lib/utils'

function StateChip({ state }: { state: string }) {
  if (state === 'running') return <Badge variant="success">running</Badge>
  if (state === 'stopped') return <Badge variant="default">stopped</Badge>
  return <Badge variant="warning">{state}</Badge>
}

function PctBar({ value }: { value: number }) {
  const col = value > 80 ? 'bg-red-500' : value > 60 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${col} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className={cn(
        'text-xs font-medium w-10 text-right',
        value > 80 ? 'text-red-500 dark:text-red-400'
          : value > 60 ? 'text-amber-500 dark:text-amber-400'
          : 'text-foreground',
      )}>
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

function EmptyState({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <div className="w-12 h-12 rounded-xl bg-muted border border-border flex items-center justify-center">
          <Icon className="w-6 h-6 text-muted-foreground" />
        </div>
        <div>
          <p className="font-medium text-foreground">No {label} found</p>
          <p className="text-sm text-muted-foreground mt-1">
            Data will appear once the agent connects to your AWS account.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

const TH = ({ children }: { children: string }) => (
  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">
    {children}
  </th>
)

const TR = ({ children, idx }: { children: React.ReactNode; idx: number }) => (
  <tr className={cn(
    'border-b border-border/40 hover:bg-muted/30 transition-colors',
    idx % 2 && 'bg-muted/10',
  )}>
    {children}
  </tr>
)

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
          <h1 className="text-2xl font-bold text-foreground">Compute</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            EC2 · Lambda · ECS — {running} instances running · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-muted border border-border rounded-xl w-fit">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                tab === t.key
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent',
              )}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded-full',
                tab === t.key ? 'bg-primary-foreground/20' : 'bg-muted-foreground/20',
              )}>
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
              (ec2 || []).length === 0
                ? <EmptyState icon={ServerOff} label="EC2 instances" />
                : (
                  <Card>
                    <CardContent className="p-0">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border">
                              {['Name', 'Type', 'State', 'Region / AZ', 'CPU', 'CPU Trend', 'Net In', 'Private IP'].map(h => (
                                <TH key={h}>{h}</TH>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(ec2 || []).map((i, idx) => (
                              <TR key={i.instance_id} idx={idx}>
                                <td className="px-4 py-3">
                                  <div className="font-medium text-foreground">{i.instance_name}</div>
                                  <div className="text-xs text-muted-foreground font-mono">
                                    {i.instance_id.slice(0, 19)}
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                                  {i.instance_type}
                                </td>
                                <td className="px-4 py-3"><StateChip state={i.state} /></td>
                                <td className="px-4 py-3">
                                  <div className="text-xs text-foreground">{i.region}</div>
                                  <div className="text-xs text-muted-foreground">{i.az}</div>
                                </td>
                                <td className="px-4 py-3 w-32">
                                  {i.state === 'running'
                                    ? <PctBar value={i.cpu} />
                                    : <span className="text-xs text-muted-foreground/40">—</span>}
                                </td>
                                <td className="px-4 py-3 w-28">
                                  {i.state === 'running' && i.metrics?.cpu ? (
                                    <Sparkline
                                      data={i.metrics.cpu.map((p: { value: number }) => ({ value: p.value }))}
                                      color={i.cpu > 80 ? '#ef4444' : i.cpu > 60 ? '#f59e0b' : '#6366f1'}
                                      height={28}
                                    />
                                  ) : <span className="text-xs text-muted-foreground/40">—</span>}
                                </td>
                                <td className="px-4 py-3 text-xs text-foreground">
                                  {i.network_in > 0 ? `${i.network_in} Mbps` : '—'}
                                </td>
                                <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                                  {i.private_ip}
                                </td>
                              </TR>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )
            )}

            {/* Lambda */}
            {tab === 'lambda' && (
              (lambda || []).length === 0
                ? <EmptyState icon={Zap} label="Lambda functions" />
                : (
                  <Card>
                    <CardContent className="p-0">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border">
                              {['Function', 'Runtime', 'Memory', 'Invocations', 'Errors', 'Avg Duration', 'Throttles', 'Trend'].map(h => (
                                <TH key={h}>{h}</TH>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(lambda || []).map((fn, idx) => {
                              const errPct = fn.invocations > 0
                                ? ((fn.errors / fn.invocations) * 100).toFixed(1)
                                : '0.0'
                              const durationS = fn.duration_avg >= 1000
                                ? `${(fn.duration_avg / 1000).toFixed(1)}s`
                                : `${fn.duration_avg} ms`
                              return (
                                <TR key={fn.function_name} idx={idx}>
                                  <td className="px-4 py-3 font-medium text-foreground max-w-[180px] truncate">
                                    {fn.function_name}
                                  </td>
                                  <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                                    {fn.runtime}
                                  </td>
                                  <td className="px-4 py-3 text-xs text-foreground">{fn.memory} MB</td>
                                  <td className="px-4 py-3 text-foreground">{fn.invocations.toLocaleString()}</td>
                                  <td className="px-4 py-3">
                                    <span className={cn(
                                      'text-xs font-medium',
                                      fn.errors > 0
                                        ? 'text-red-500 dark:text-red-400'
                                        : 'text-emerald-600 dark:text-emerald-400',
                                    )}>
                                      {fn.errors}
                                      {fn.errors > 0 && (
                                        <span className="text-muted-foreground"> ({errPct}%)</span>
                                      )}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-xs">
                                    <span className={fn.duration_avg > 2000
                                      ? 'text-amber-500 dark:text-amber-400'
                                      : 'text-foreground'}>
                                      {durationS}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3">
                                    {fn.throttles > 0
                                      ? <Badge variant="warning">{fn.throttles}</Badge>
                                      : <span className="text-xs text-emerald-600 dark:text-emerald-400">0</span>}
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
                                </TR>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )
            )}

            {/* ECS */}
            {tab === 'ecs' && (
              (ecs || []).length === 0
                ? <EmptyState icon={Layers} label="ECS services" />
                : (
                  <Card>
                    <CardContent className="p-0">
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-border">
                              {['Cluster', 'Service', 'Tasks', 'Status', 'CPU', 'Memory'].map(h => (
                                <TH key={h}>{h}</TH>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(ecs || []).map((svc, idx) => (
                              <TR key={`${svc.cluster}-${svc.service_name}`} idx={idx}>
                                <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                                  {svc.cluster}
                                </td>
                                <td className="px-4 py-3 font-medium text-foreground">{svc.service_name}</td>
                                <td className="px-4 py-3">
                                  <span className={svc.running < svc.desired
                                    ? 'text-red-500 dark:text-red-400 font-semibold'
                                    : 'text-emerald-600 dark:text-emerald-400 font-semibold'
                                  }>
                                    {svc.running}
                                  </span>
                                  <span className="text-muted-foreground text-xs">/{svc.desired}</span>
                                  {svc.pending > 0 && (
                                    <span className="text-amber-500 dark:text-amber-400 text-xs ml-1">
                                      (+{svc.pending} pending)
                                    </span>
                                  )}
                                </td>
                                <td className="px-4 py-3"><Badge variant="success">{svc.status}</Badge></td>
                                <td className="px-4 py-3 w-36"><PctBar value={svc.cpu} /></td>
                                <td className="px-4 py-3 w-36"><PctBar value={svc.memory} /></td>
                              </TR>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
