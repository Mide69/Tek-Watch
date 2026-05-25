'use client'

import { useEffect, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import {
  Activity, AlertTriangle, DollarSign, Server,
  CheckCircle, TrendingDown, Zap,
} from 'lucide-react'
import { formatCurrency, formatRelativeTime } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import {
  MOCK_OVERVIEW, MOCK_COST_SUMMARY, MOCK_EC2, MOCK_ALERTS,
} from '@/lib/mockData'
/** Pure-SVG sparkline — no Recharts, no ResizeObserver, no renderer issues */
function MiniAreaChart({ data, color }: { data: { v: number }[]; color: string }) {
  const W = 200, H = 40
  const min = Math.min(...data.map(d => d.v))
  const max = Math.max(...data.map(d => d.v)) || 1
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W
    const y = H - ((d.v - min) / (max - min)) * (H - 4) - 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const polyline = pts.join(' ')
  const area = `0,${H} ${polyline} ${W},${H}`
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={40} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={`sg-${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#sg-${color.replace('#','')})`} />
      <polyline points={polyline} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

// Mini sparkline data
const cpuSpark    = [72,68,74,81,77,85,88,92].map(v => ({ v }))
const costSpark   = [135,141,138,148,152,146,158,162].map(v => ({ v }))
const alarmSpark  = [1,1,2,2,3,3,3,3].map(v => ({ v }))
const resourceSpark = [820,828,831,837,839,843,845,847].map(v => ({ v }))

export default function OverviewPage() {
  const { loading: authLoading, customerId } = useAuth()
  const [data, setData]       = useState<typeof MOCK_OVERVIEW | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authLoading) load()
  }, [authLoading])

  const load = async () => {
    try {
      const { default: api } = await import('@/lib/api')
      const r = await api.getOverview()
      setData(r)
    } catch {
      setData(MOCK_OVERVIEW)
    } finally {
      setLoading(false)
    }
  }

  const activeAlerts = MOCK_ALERTS.filter(a => a.status === 'active')

  if (authLoading || loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500" />
        </div>
      </DashboardLayout>
    )
  }

  const d = data || MOCK_OVERVIEW

  return (
    <DashboardLayout customerId={customerId || 'TT-DEMO'}>
      <div className="space-y-6 animate-fade-in">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Overview</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              Acme Technologies Ltd · {new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })}
            </p>
          </div>
          {/* Agent status pill */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium ${
            d.agent_status.status === 'healthy'
              ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/25 text-amber-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${d.agent_status.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
            Agent {d.agent_status.status}
            {d.agent_status.last_seen && (
              <span className="opacity-70 ml-1">· {formatRelativeTime(d.agent_status.last_seen)}</span>
            )}
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              title: 'Total Resources',
              value: d.total_resources.toLocaleString(),
              change: '+7 this week',
              positive: true,
              icon: Server,
              color: 'text-blue-400',
              iconBg: 'bg-blue-500/10 border-blue-500/20',
              spark: resourceSpark,
              sparkColor: '#3b82f6',
            },
            {
              title: 'Active Alarms',
              value: d.active_alarms.toString(),
              change: '1 critical',
              positive: false,
              icon: AlertTriangle,
              color: 'text-red-400',
              iconBg: 'bg-red-500/10 border-red-500/20',
              spark: alarmSpark,
              sparkColor: '#f87171',
            },
            {
              title: 'Security Findings',
              value: d.security_findings.toString(),
              change: '1 high severity',
              positive: false,
              icon: Activity,
              color: 'text-amber-400',
              iconBg: 'bg-amber-500/10 border-amber-500/20',
              spark: [1,1,1,1,1,2,2,2].map(v => ({ v })),
              sparkColor: '#fbbf24',
            },
            {
              title: 'Est. Monthly Cost',
              value: formatCurrency(d.estimated_monthly_cost),
              change: '↓ 3.2% vs last month',
              positive: true,
              icon: DollarSign,
              color: 'text-emerald-400',
              iconBg: 'bg-emerald-500/10 border-emerald-500/20',
              spark: costSpark,
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
                <div className={`text-xs ${c.positive ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {c.change}
                </div>
                <div className="mt-3 -mx-1">
                  <MiniAreaChart data={c.spark} color={c.sparkColor} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Active alerts + top CPU */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Active alerts — full width left 2/3 */}
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

          {/* Top CPU instances */}
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-white">Top CPU</h3>
                <span className="text-xs text-slate-500">EC2</span>
              </div>
              <div className="space-y-3">
                {MOCK_EC2
                  .filter(i => i.state === 'running')
                  .sort((a, b) => b.cpu - a.cpu)
                  .slice(0, 6)
                  .map(i => (
                    <div key={i.instance_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-300 truncate max-w-[60%]">{i.instance_name}</span>
                        <span className={`text-xs font-semibold ${i.cpu > 80 ? 'text-red-400' : i.cpu > 60 ? 'text-amber-400' : 'text-slate-300'}`}>
                          {i.cpu.toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${i.cpu > 80 ? 'bg-red-500' : i.cpu > 60 ? 'bg-amber-500' : 'bg-indigo-500'}`}
                          style={{ width: `${i.cpu}%` }} />
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Cost trend + AI insight */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 30-day cost sparkline */}
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-semibold text-white">Daily Spend</h3>
                    <p className="text-xs text-slate-500 mt-0.5">Last 30 days</p>
                  </div>
                  <div className="flex items-center gap-1 text-emerald-400 text-xs font-medium">
                    <TrendingDown className="w-3.5 h-3.5" />
                    ↓ 3.2% vs last month
                  </div>
                </div>
                {(() => {
                  const daily = MOCK_COST_SUMMARY.daily_costs
                  const maxC  = Math.max(...daily.map(d => d.cost))
                  return (
                    <div className="flex items-end gap-1 h-24">
                      {daily.map((d, i) => (
                        <div key={i} className="flex-1 rounded-sm"
                          style={{
                            height: `${(d.cost / maxC) * 100}%`,
                            background: i === daily.length - 1 ? '#f97316' : '#6366f1',
                            opacity: i === daily.length - 1 ? 1 : 0.55,
                          }}
                          title={`$${d.cost.toFixed(2)}`}
                        />
                      ))}
                    </div>
                  )
                })()}
                <div className="flex justify-between text-xs text-slate-500 mt-2">
                  <span>30 days ago</span>
                  <span>Today</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* AI insight card */}
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
                <span className="text-indigo-400 font-medium">Recommendation:</span> Investigate recent dependency changes.
                Consider enabling Lambda SnapStart.
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
                { region: 'eu-west-2', name: 'EU West (London)',     resources: 642, pct: 76 },
                { region: 'eu-west-1', name: 'EU West (Ireland)',    resources: 143, pct: 17 },
                { region: 'us-east-1', name: 'US East (N. Virginia)',resources:  62, pct:  7 },
              ].map(r => (
                <div key={r.region} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono text-slate-400">{r.region}</span>
                    <span className="text-xs text-slate-500">{r.resources} resources</span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">{r.name}</p>
                  <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${r.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  )
}
