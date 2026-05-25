'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { Sparkline, BarChart } from '@/components/ui/MiniChart'
import {
  Activity, AlertTriangle, DollarSign, Server,
  CheckCircle, TrendingDown, Zap,
} from 'lucide-react'
import { formatCurrency, formatRelativeTime } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useOverview, useAlerts, useEC2 } from '@/hooks/useData'

export default function OverviewPage() {
  const { customerId }  = useAuth()
  const { timeRange }   = useDashboard()
  const { data, isLoading } = useOverview()
  const { data: alerts }    = useAlerts()
  const { data: ec2 }       = useEC2()

  if (isLoading || !data) {
    return (
      <DashboardLayout customerId={customerId || 'TT-DEMO'}>
        <div className="space-y-6">
          <div className="h-8 w-48 bg-white/[0.06] rounded animate-pulse" />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const activeAlerts = (alerts || []).filter(a => a.status === 'active')
  const runningEC2   = (ec2 || []).filter(i => i.state === 'running')
    .sort((a, b) => b.cpu - a.cpu).slice(0, 6)

  const costBars = data.cost_trend.map(d => ({ value: d.cost, label: d.label }))

  return (
    <DashboardLayout customerId={customerId || 'TT-DEMO'}>
      <div className="space-y-6 animate-fade-in">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-white">Overview</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              Acme Technologies Ltd · {TIME_RANGE_LABELS[timeRange]}
            </p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium ${
            data.agent_status.status === 'healthy'
              ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/25 text-amber-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${
              data.agent_status.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'
            } animate-pulse`} />
            Agent {data.agent_status.status}
            {data.agent_status.last_seen && (
              <span className="opacity-70 ml-1">· {formatRelativeTime(data.agent_status.last_seen)}</span>
            )}
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              title: 'Total Resources',
              value: data.total_resources.toLocaleString(),
              change: '+7 this period',
              positive: true,
              icon: Server,
              color: 'text-blue-400',
              iconBg: 'bg-blue-500/10 border-blue-500/20',
              spark: data.cost_trend.map((_, i) => ({ value: 820 + i * 1.5 })),
              sparkColor: '#3b82f6',
            },
            {
              title: 'Active Alarms',
              value: data.active_alarms.toString(),
              change: `${activeAlerts.filter(a => a.severity === 'critical').length} critical`,
              positive: false,
              icon: AlertTriangle,
              color: 'text-red-400',
              iconBg: 'bg-red-500/10 border-red-500/20',
              spark: data.cost_trend.map((_, i) => ({ value: i < 4 ? 1 : i < 8 ? 2 : 3 })),
              sparkColor: '#f87171',
            },
            {
              title: 'Security Findings',
              value: data.security_findings.toString(),
              change: '1 high severity',
              positive: false,
              icon: Activity,
              color: 'text-amber-400',
              iconBg: 'bg-amber-500/10 border-amber-500/20',
              spark: data.cost_trend.map((_, i) => ({ value: i < 6 ? 1 : 2 })),
              sparkColor: '#fbbf24',
            },
            {
              title: 'Est. Monthly Cost',
              value: formatCurrency(data.estimated_monthly_cost),
              change: '↓ 3.2% vs last month',
              positive: true,
              icon: DollarSign,
              color: 'text-emerald-400',
              iconBg: 'bg-emerald-500/10 border-emerald-500/20',
              spark: costBars,
              sparkColor: '#34d399',
            },
          ].map(c => (
            <Card key={c.title} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-slate-400">{c.title}</span>
                  <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${c.iconBg}`}>
                    <c.icon className={`w-3.5 h-3.5 ${c.color}`} />
                  </div>
                </div>
                <div className={`text-2xl font-bold mb-1 ${c.color}`}>{c.value}</div>
                <div className={`text-xs ${c.positive ? 'text-emerald-400' : 'text-slate-400'}`}>{c.change}</div>
                <div className="mt-3 -mx-1">
                  <Sparkline data={c.spark} color={c.sparkColor} height={36} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Active alerts + Top CPU */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-white">Active Alerts</h3>
                  <Badge variant="error">{activeAlerts.length} active</Badge>
                </div>
                <div className="space-y-3">
                  {activeAlerts.length === 0 ? (
                    <div className="flex items-center gap-2 text-emerald-400 py-4">
                      <CheckCircle className="h-5 w-5" />
                      <p className="text-sm">No active alerts — infrastructure looks healthy</p>
                    </div>
                  ) : activeAlerts.map(a => (
                    <div key={a.alert_id} className={`flex items-start gap-3 p-3 rounded-lg border ${
                      a.severity === 'critical'
                        ? 'bg-red-500/5 border-red-500/20'
                        : 'bg-amber-500/5 border-amber-500/20'
                    }`}>
                      <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 animate-pulse ${
                        a.severity === 'critical' ? 'bg-red-500' : 'bg-amber-500'
                      }`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <Badge variant={a.severity === 'critical' ? 'error' : 'warning'}>
                            {a.severity.toUpperCase()}
                          </Badge>
                          {a.type === 'ai_anomaly' && <Badge variant="ai">✦ AI Detected</Badge>}
                          <span className="text-xs text-slate-500">{a.service}</span>
                        </div>
                        <p className="text-sm text-slate-300 leading-snug">{a.description}</p>
                        <p className="text-xs text-slate-500 mt-1">{formatRelativeTime(a.triggered_at)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Top CPU */}
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-white">Top CPU</h3>
                <span className="text-xs text-slate-500">EC2</span>
              </div>
              <div className="space-y-3">
                {runningEC2.map(i => (
                  <div key={i.instance_id}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-slate-300 truncate max-w-[60%]">{i.instance_name}</span>
                      <span className={`text-xs font-semibold ${i.cpu > 80 ? 'text-red-400' : i.cpu > 60 ? 'text-amber-400' : 'text-slate-300'}`}>
                        {i.cpu.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${i.cpu > 80 ? 'bg-red-500' : i.cpu > 60 ? 'bg-amber-500' : 'bg-indigo-500'}`}
                        style={{ width: `${i.cpu}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Cost trend + AI insight */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white">Daily Spend</h3>
                    <p className="text-xs text-slate-500 mt-0.5">{TIME_RANGE_LABELS[timeRange]}</p>
                  </div>
                  <div className="flex items-center gap-1 text-emerald-400 text-xs font-medium">
                    <TrendingDown className="w-3.5 h-3.5" />
                    ↓ 3.2% vs last month
                  </div>
                </div>
                <BarChart data={costBars} height={96} />
                <div className="flex justify-between text-xs text-slate-500 mt-2">
                  <span>{data.cost_trend[0]?.label ?? 'Earlier'}</span>
                  <span>Today</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-indigo-500/20 bg-indigo-600/5">
            <CardContent className="p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/30 flex items-center justify-center">
                  <Zap className="w-3.5 h-3.5 text-indigo-400" />
                </div>
                <span className="text-xs font-semibold text-indigo-400">AI Insight</span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed mb-4">
                Lambda spend is up <span className="text-amber-400 font-semibold">+38.7%</span> month-over-month.
                The <span className="font-medium text-white">acme-image-processor</span> function is responsible —
                cold-start duration spiked 340% in the last 2 hours.
              </p>
              <p className="text-xs text-slate-500">
                <span className="text-indigo-400 font-medium">Recommendation:</span> Investigate recent dependency
                changes. Consider enabling Lambda SnapStart.
              </p>
              <div className="mt-4 pt-4 border-t border-white/[0.06] flex items-center gap-1.5 text-xs text-slate-500">
                <Zap className="w-3 h-3 text-indigo-400" />
                Powered by Claude AI
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Region breakdown */}
        <Card>
          <CardContent className="p-5">
            <h3 className="font-semibold text-white mb-4">Resources by Region</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                { region: 'eu-west-2', name: 'EU West (London)',      pct: 76 },
                { region: 'eu-west-1', name: 'EU West (Ireland)',     pct: 17 },
                { region: 'us-east-1', name: 'US East (N. Virginia)', pct:  7 },
              ].map(r => {
                const count = Math.round((data.total_resources * r.pct) / 100)
                return (
                  <div key={r.region} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono text-slate-400">{r.region}</span>
                      <span className="text-xs text-slate-500">{count} resources</span>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">{r.name}</p>
                    <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${r.pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  )
}
