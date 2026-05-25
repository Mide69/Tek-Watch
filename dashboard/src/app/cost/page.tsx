'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { DollarSign, TrendingUp, TrendingDown, Zap } from 'lucide-react'
import { formatCurrency } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useCost } from '@/hooks/useData'

const SERVICE_COLORS = ['#6366f1','#3b82f6','#f59e0b','#10b981','#f97316','#a78bfa','#06b6d4','#ec4899']

function DailyCostBars({ data }: { data: { cost: number; label?: string; time?: string }[] }) {
  const maxC = Math.max(...data.map(d => d.cost)) || 1
  return (
    <div>
      <div className="flex items-end gap-[3px] h-48">
        {data.map((d, i) => (
          <div
            key={i}
            className="flex-1 rounded-sm transition-all cursor-default"
            style={{
              height:     `${Math.max((d.cost / maxC) * 100, 2)}%`,
              background: i === data.length - 1 ? '#f97316' : '#6366f1',
              opacity:    i === data.length - 1 ? 1 : 0.6,
            }}
            title={`${d.label ?? d.time ?? ''}: ${formatCurrency(d.cost)}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-slate-500 mt-2">
        <span>{data[0]?.label ?? 'Earlier'}</span>
        <span className="text-orange-400">Today</span>
      </div>
    </div>
  )
}

function ServiceDonut({ data }: { data: { aws_service: string; mtd_cost: number }[] }) {
  const total = data.reduce((s, d) => s + d.mtd_cost, 0) || 1
  const R = 70, CX = 90, CY = 90
  const CIRC = 2 * Math.PI * R

  let offset = 0
  const segments = data.map((d, i) => {
    const frac = d.mtd_cost / total
    const seg  = { frac, offset, color: SERVICE_COLORS[i % SERVICE_COLORS.length] }
    offset += frac
    return seg
  })

  return (
    <div className="flex items-center gap-6">
      <svg width={180} height={180} viewBox="0 0 180 180">
        {segments.map((s, i) => (
          <circle
            key={i}
            cx={CX} cy={CY} r={R}
            fill="none"
            stroke={s.color}
            strokeWidth={22}
            strokeDasharray={`${s.frac * CIRC} ${CIRC}`}
            strokeDashoffset={-s.offset * CIRC}
            transform={`rotate(-90 ${CX} ${CY})`}
          />
        ))}
        <text x={CX} y={CY - 6}  textAnchor="middle" fill="#f8fafc" fontSize={14} fontWeight="700">
          {formatCurrency(total)}
        </text>
        <text x={CX} y={CY + 12} textAnchor="middle" fill="#64748b" fontSize={10}>
          MTD Total
        </text>
      </svg>
      <div className="space-y-1.5 flex-1">
        {data.slice(0, 6).map((d, i) => (
          <div key={d.aws_service} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: SERVICE_COLORS[i % SERVICE_COLORS.length] }} />
            <span className="text-xs text-slate-400 truncate flex-1">{d.aws_service}</span>
            <span className="text-xs font-medium text-slate-200">{formatCurrency(d.mtd_cost)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CostPage() {
  const { customerId }       = useAuth()
  const { timeRange }        = useDashboard()
  const { data, isLoading }  = useCost()

  if (isLoading || !data) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-40 bg-white/[0.06] rounded animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[0,1,2].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const { summary, breakdown } = data
  const { mtd_total: mtd, last_month_total: last, forecasted_monthly: forecast, daily_costs } = summary
  const trendUp  = mtd > last
  const trendPct = last > 0 ? Math.abs(((mtd - last) / last) * 100).toFixed(1) : '0'

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Cost Analysis</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            AWS spend overview and per-service breakdown · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              label: 'Month-to-Date',
              value: formatCurrency(mtd),
              sub:   `${trendUp ? '+' : '−'}${trendPct}% vs last month`,
              icon:  trendUp ? TrendingUp : TrendingDown,
              color: trendUp ? 'text-red-400' : 'text-emerald-400',
              bg:    trendUp ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20',
            },
            {
              label: 'Forecasted Monthly',
              value: formatCurrency(forecast),
              sub:   'Based on current trend',
              icon:  DollarSign,
              color: 'text-amber-400',
              bg:    'bg-amber-500/10 border-amber-500/20',
            },
            {
              label: 'Last Month Total',
              value: formatCurrency(last),
              sub:   'Previous billing period',
              icon:  DollarSign,
              color: 'text-slate-300',
              bg:    'bg-white/[0.04] border-white/[0.08]',
            },
          ].map(c => (
            <Card key={c.label}>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-slate-400">{c.label}</span>
                  <div className={`w-8 h-8 rounded-lg border flex items-center justify-center ${c.bg}`}>
                    <c.icon className={`w-4 h-4 ${c.color}`} />
                  </div>
                </div>
                <div className={`text-2xl font-bold mb-1 ${c.color}`}>{c.value}</div>
                <p className="text-xs text-slate-500">{c.sub}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Daily cost chart — responds to time range */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Daily Spend — {TIME_RANGE_LABELS[timeRange]}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DailyCostBars data={daily_costs} />
          </CardContent>
        </Card>

        {/* Breakdown + donut */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-slate-400" />
                <CardTitle className="text-base">Cost by Service</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <ServiceDonut data={breakdown.breakdown.map(d => ({ aws_service: d.aws_service, mtd_cost: d.mtd_cost }))} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Service Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakdown.breakdown.map(svc => {
                  const pct = mtd > 0 ? ((svc.mtd_cost / mtd) * 100).toFixed(1) : '0'
                  return (
                    <div key={svc.aws_service} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium text-slate-200 truncate max-w-[55%]">{svc.aws_service}</span>
                        <div className="flex items-center gap-2">
                          {svc.vs_last_month !== undefined && (
                            <span className={`text-xs ${svc.vs_last_month > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                              {svc.vs_last_month > 0 ? '+' : ''}{svc.vs_last_month.toFixed(1)}%
                            </span>
                          )}
                          <span className="font-bold text-white">{formatCurrency(svc.mtd_cost)}</span>
                        </div>
                      </div>
                      <div className="w-full bg-white/[0.06] rounded-full h-1.5">
                        <div className="bg-indigo-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* AI cost insight */}
        <Card className="border-indigo-500/20 bg-indigo-600/5">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-600/30 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Zap className="w-4 h-4 text-indigo-400" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-indigo-400">AI Cost Insight</span>
                  <span className="text-xs text-slate-500">· Powered by Claude</span>
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">
                  Your <span className="text-amber-400 font-medium">Lambda spend is up 38.7% month-over-month</span>, driven by
                  the <span className="font-medium text-white">acme-image-processor</span> function — invocations are up but
                  cold-start duration has also spiked 340%, suggesting a recent package change. Your overall bill is trending
                  toward <span className="font-medium text-white">{formatCurrency(forecast)}</span> this month,
                  which is 1.6% below last month&apos;s total — the savings come from EC2 right-sizing completed last week.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
