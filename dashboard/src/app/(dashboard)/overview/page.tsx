'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Sparkline, BarChart } from '@/components/ui/MiniChart'
import {
  Activity, AlertTriangle, DollarSign, Server,
  CheckCircle, TrendingDown, TrendingUp,
} from 'lucide-react'
import { formatCurrency, formatRelativeTime, fmtPercent } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import { useProfile } from '@/hooks/useProfile'
import { useFixtureView } from '@/hooks/useFixtureView'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useOverview, useAlerts, useEC2, useSecurity } from '@/hooks/useData'
import { cn } from '@/lib/utils'

// Region display names. The agent reports region codes; only the codes an
// account actually uses are ever rendered, so this is a lookup, not a list of
// regions to show.
const REGION_NAMES: Record<string, string> = {
  'us-east-1': 'US East (N. Virginia)',   'us-east-2': 'US East (Ohio)',
  'us-west-1': 'US West (N. California)', 'us-west-2': 'US West (Oregon)',
  'eu-west-1': 'EU West (Ireland)',       'eu-west-2': 'EU West (London)',
  'eu-west-3': 'EU West (Paris)',         'eu-central-1': 'EU Central (Frankfurt)',
  'eu-north-1': 'EU North (Stockholm)',   'eu-south-1': 'EU South (Milan)',
  'ap-south-1': 'Asia Pacific (Mumbai)',  'ap-northeast-1': 'Asia Pacific (Tokyo)',
  'ap-northeast-2': 'Asia Pacific (Seoul)', 'ap-northeast-3': 'Asia Pacific (Osaka)',
  'ap-southeast-1': 'Asia Pacific (Singapore)', 'ap-southeast-2': 'Asia Pacific (Sydney)',
  'ca-central-1': 'Canada (Central)',     'sa-east-1': 'South America (São Paulo)',
  'me-south-1': 'Middle East (Bahrain)',  'af-south-1': 'Africa (Cape Town)',
  'global': 'Global services',
}

// The shell — sidebar, Home, Sign out — depends only on who is signed in,
// never on overview data, so it renders even when the content below throws.
// This is the first page a customer lands on after signing in, which makes
// it the worst possible place to lose the ability to sign out or go home.
// See the identical note in networking/page.tsx for why this split exists.
export default function OverviewPage() {
  const { customerId } = useAuth()
  return (
    <DashboardLayout customerId={customerId || undefined}>
      <ErrorBoundary>
        <OverviewContent customerId={customerId} />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function OverviewContent({ customerId }: { customerId: string | null }) {
  // Company name where they have set one; the raw Customer ID is a poor
  // thing to greet someone with on their own dashboard.
  const { data: profile } = useProfile()
  // Several flourishes on this page are fixture copy with no data behind them:
  // a hardcoded "+7 this period", a fixed "3.2% vs last month", and an AI
  // Insight naming a Lambda function in somebody else's account. They read as
  // findings about the customer's own estate. Shown only where they are
  // honestly labelled sample, which is the demo.
  const fixtureView = useFixtureView()
  const { timeRange }   = useDashboard()
  const { data }   = useOverview()
  const { data: alertsData }  = useAlerts()
  const { data: ec2 }         = useEC2()
  const { data: security }    = useSecurity()
  const guardduty = security?.guardduty ?? []

  if (!data) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-muted rounded animate-pulse" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map(i => <CardSkeleton key={i} />)}
        </div>
      </div>
    )
  }

  // Real region counts from the agent, biggest first. The bar is scaled
  // against the largest region rather than the total, so a long tail of
  // single-resource regions stays visible instead of rounding to nothing.
  const regions = (data.resources_by_region ?? []) as Array<{ region: string; count: number }>
  const regionMax = regions.reduce((m, r) => Math.max(m, r.count), 0)

  const alerts = alertsData?.alerts ?? []
  const activeAlerts = (alerts as Array<{ status: string; severity: string; type?: string; alert_id: string; service?: string; description?: string; triggered_at?: string }>)
    .filter(a => a.status === 'active')
  const runningEC2 = (ec2 || []).filter(i => i.state === 'running')
    .sort((a, b) => (b.cpu ?? 0) - (a.cpu ?? 0)).slice(0, 6)

  // The API's overview does not return cost_trend — only the mock has it — so
  // this threw before the page could paint once real data started arriving.
  // An empty sparkline is the honest rendering of a series we do not have.
  const trend: { cost: number; label: string }[] = Array.isArray(data.cost_trend) ? data.cost_trend : []
  const costBars = trend.map(d => ({ value: d.cost, label: d.label }))

  return (
      <div className="space-y-6 animate-fade-in">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Overview</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              {profile?.display_name || customerId || 'Demo'} · {TIME_RANGE_LABELS[timeRange]}
            </p>
          </div>
          <div className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-medium',
            data.agent_status.status === 'healthy'
              ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-600 dark:text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/25 text-amber-600 dark:text-amber-400',
          )}>
            <span className={cn(
              'w-1.5 h-1.5 rounded-full',
              data.agent_status.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500',
            )} />
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
              change: fixtureView ? '+7 this period' : '',
              positive: true,
              icon: Server,
              colorClass: 'text-blue-500 dark:text-blue-400',
              iconBg: 'bg-blue-500/10 border-blue-500/20',
              spark: trend.map((_, i) => ({ value: 820 + i * 1.5 })),
              sparkColor: '#3b82f6',
            },
            {
              title: 'Active Alarms',
              value: data.active_alarms.toString(),
              change: `${activeAlerts.filter(a => a.severity === 'critical').length} critical`,
              positive: false,
              icon: AlertTriangle,
              colorClass: 'text-red-500 dark:text-red-400',
              iconBg: 'bg-red-500/10 border-red-500/20',
              spark: trend.map((_, i) => ({ value: i < 4 ? 1 : i < 8 ? 2 : 3 })),
              sparkColor: '#ef4444',
            },
            {
              title: 'GuardDuty Findings',
              value: guardduty.length.toString(),
              change: `${guardduty.filter(f => f.severity.toUpperCase() === 'HIGH').length} high severity`,
              positive: false,
              icon: Activity,
              colorClass: 'text-amber-500 dark:text-amber-400',
              iconBg: 'bg-amber-500/10 border-amber-500/20',
              spark: [],
              sparkColor: '#f59e0b',
            },
            {
              title: 'Est. Monthly Cost',
              value: formatCurrency(data.estimated_monthly_cost),
              change: fixtureView ? '↓ 3.2% vs last month' : '',
              positive: true,
              icon: DollarSign,
              colorClass: 'text-emerald-600 dark:text-emerald-400',
              iconBg: 'bg-emerald-500/10 border-emerald-500/20',
              spark: costBars,
              sparkColor: '#10b981',
            },
          ].map(c => (
            <Card key={c.title} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-medium text-muted-foreground">{c.title}</span>
                  <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${c.iconBg}`}>
                    <c.icon className={`w-3.5 h-3.5 ${c.colorClass}`} />
                  </div>
                </div>
                <div className={`text-2xl font-bold mb-1 ${c.colorClass}`}>{c.value}</div>
                <div className={`text-xs ${c.positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>
                  {c.change}
                </div>
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
                  <h3 className="font-semibold text-foreground">Active Alerts</h3>
                  <Badge variant="error">{activeAlerts.length} active</Badge>
                </div>
                <div className="space-y-3">
                  {activeAlerts.length === 0 ? (
                    <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 py-4">
                      <CheckCircle className="h-5 w-5" />
                      <p className="text-sm">No active alerts — infrastructure looks healthy</p>
                    </div>
                  ) : activeAlerts.map(a => (
                    <div
                      key={a.alert_id}
                      className={cn(
                        'flex items-start gap-3 p-3 rounded-lg border',
                        a.severity === 'critical'
                          ? 'bg-red-500/5 border-red-500/20'
                          : 'bg-amber-500/5 border-amber-500/20',
                      )}
                    >
                      <div className={cn(
                        'w-2 h-2 rounded-full mt-1.5 flex-shrink-0',
                        a.severity === 'critical' ? 'bg-red-500' : 'bg-amber-500',
                      )} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <Badge variant={a.severity === 'critical' ? 'error' : 'warning'}>
                            {a.severity.toUpperCase()}
                          </Badge>
                          {a.type === 'ai_anomaly' && <Badge variant="ai">Anomaly</Badge>}
                          <span className="text-xs text-muted-foreground">{a.service}</span>
                        </div>
                        <p className="text-sm text-foreground leading-snug">{a.description}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {a.triggered_at ? formatRelativeTime(a.triggered_at) : ''}
                        </p>
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
                <h3 className="font-semibold text-foreground">Top CPU</h3>
                <span className="text-xs text-muted-foreground">EC2</span>
              </div>
              <div className="space-y-3">
                {runningEC2.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">No running instances</p>
                ) : runningEC2.map(i => (
                  <div key={i.instance_id}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-foreground truncate max-w-[60%]">{i.instance_name}</span>
                      <span className={cn(
                        'text-xs font-semibold',
                        (i.cpu ?? 0) > 80 ? 'text-red-500 dark:text-red-400'
                          : (i.cpu ?? 0) > 60 ? 'text-amber-500 dark:text-amber-400'
                          : 'text-foreground',
                      )}>
                        {fmtPercent(i.cpu)}
                      </span>
                    </div>
                    <div className="h-1 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          (i.cpu ?? 0) > 80 ? 'bg-red-500' : (i.cpu ?? 0) > 60 ? 'bg-amber-500' : 'bg-primary',
                        )}
                        style={{ width: `${i.cpu ?? 0}%` }}
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
                    <h3 className="font-semibold text-foreground">Daily Spend</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">{TIME_RANGE_LABELS[timeRange]}</p>
                  </div>
                  {fixtureView && (
                    <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                      <TrendingDown className="w-3.5 h-3.5" />
                      ↓ 3.2% vs last month
                    </div>
                  )}
                </div>
                <BarChart data={costBars} height={96} formatValue={formatCurrency} />
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>{trend[0]?.label ?? 'Earlier'}</span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-3 h-[2px] rounded-full bg-foreground/50" />
                    Trend · Today
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Hand-written example of the feature, not a generated analysis: it
              names a Lambda function in an account that is not the customer's.
              Shown only where the page is honestly labelled as sample data. */}
          {fixtureView && (
          <Card>
            <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-muted-foreground" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Cost insight</span>
                </div>
                <p className="text-sm text-foreground leading-relaxed mb-4">
                  Lambda spend is up{' '}
                  <span className="text-amber-500 dark:text-amber-400 font-semibold">+38.7%</span>{' '}
                  month-over-month. The{' '}
                  <span className="font-medium">acme-image-processor</span> function is responsible
                  — cold-start duration spiked 340% in the last 2 hours.
                </p>
                <p className="text-xs text-muted-foreground">
                  <span className="text-primary font-medium">Recommendation:</span> Investigate recent
                  dependency changes. Consider enabling Lambda SnapStart.
                </p>
              </CardContent>
          </Card>
          )}
        </div>

        {/* Region breakdown */}
        <Card>
          <CardContent className="p-5">
            <h3 className="font-semibold text-foreground mb-4">Resources by Region</h3>
            {/* This panel used to be three hardcoded regions — eu-west-2,
                eu-west-1, us-east-1 — split 76/17/7, with the counts derived
                from that split rather than measured. It queried nothing. An
                account in different regions was shown a breakdown of regions
                it did not use, and the bars beside them were drawn from
                constants in this file. It reported zero only because the
                total it multiplied was itself broken; the moment that was
                fixed it would have started inventing confident numbers. */}
            {regions.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No resources reported yet. Regions appear here once your agent completes a collection.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {regions.map(r => {
                  const width = regionMax > 0 ? Math.round((r.count / regionMax) * 100) : 0
                  return (
                    <div key={r.region} className="p-4 rounded-xl bg-muted/50 border border-border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono text-muted-foreground">{r.region}</span>
                        <span className="text-xs text-muted-foreground">
                          {r.count} {r.count === 1 ? 'resource' : 'resources'}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mb-2">{REGION_NAMES[r.region] ?? r.region}</p>
                      <div className="h-1 bg-muted rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: `${width}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>

      </div>
  )
}
