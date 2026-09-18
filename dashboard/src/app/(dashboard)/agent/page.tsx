'use client'

import { useEffect, useState } from 'react'
import axios from 'axios'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Activity, CheckCircle, Radio, Clock, AlertTriangle, Download } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useAgent } from '@/hooks/useData'
import { formatRelativeTime, fmtCount } from '@/lib/utils'
import { useFixtureView } from '@/hooks/useFixtureView'
import { SetupGuide } from '@/components/agent/SetupGuide'
import { AgentKeyPanel } from '@/components/agent/AgentKeyPanel'
import { useShowingSampleData } from '@/lib/dataSource'
import apiClient from '@/lib/api'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

function DeployAgentCard({ customerId }: { customerId: string }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const fixtureView = useFixtureView()

  async function handleDownload() {
    setError('')
    setDownloading(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/agent/cfn-template`, {
        headers: { Authorization: `Bearer ${apiClient.getToken()}` },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `tek-watch-agent-${customerId}.yaml`
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Could not download the template right now. Please try again shortly.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Card className="border-indigo-500/20 bg-indigo-500/5">
      <CardContent className="p-5">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="font-semibold text-foreground mb-1">Deploy your monitoring agent</h3>
            <p className="text-sm text-muted-foreground max-w-xl">
              Download your CloudFormation template and deploy the read-only agent into
              your own AWS account. Takes about 30 minutes, no inbound firewall changes
              needed.
            </p>
            {error && <p className="text-sm text-red-500 dark:text-red-400 mt-2">{error}</p>}
          </div>
          {fixtureView ? (
            <span className="text-xs text-muted-foreground px-3 py-2">
              Available on a real account, not this demo
            </span>
          ) : (
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-lg disabled:opacity-50 transition-colors flex-shrink-0"
            >
              <Download className="w-4 h-4" />
              {downloading ? 'Preparing…' : 'Download CloudFormation Template'}
            </button>
          )}
        </div>
        {!fixtureView && (
          <div className="mt-4 pt-4 border-t border-border">
            <AgentKeyPanel />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// The shell — sidebar, Home, Sign out — depends only on who is signed in,
// never on agent data, so it renders even when the content below throws. See
// the identical note in networking/page.tsx for why this split exists.
export default function AgentPage() {
  const { customerId } = useAuth()
  return (
    <DashboardLayout customerId={customerId || undefined}>
      <ErrorBoundary>
        <AgentContent customerId={customerId} />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function AgentContent({ customerId }: { customerId: string | null }) {
  const { data: a } = useAgent()

  // A real account with no agent must not be shown a healthy one.
  //
  // Every other page labels its sample figures and moves on, which is fair for
  // a resource count. This page is different: "Healthy", "Up 2,184h", "18/18
  // collectors" is a claim about the customer's own infrastructure, and a
  // caption above it does not stop it reading as fact. Someone with nothing
  // deployed was being told their monitoring was fine.
  //
  // Demo visitors still get the full sample view — that is the point of the
  // demo, and DemoBadge says so.
  const showingSample = useShowingSampleData()
  const isDemo = useFixtureView()
  const notConnected = showingSample && isDemo === false
  // Reachable in both states. Someone with a working agent still needs to know
  // how to remove it, and someone with none needs to know what they are about
  // to run before they run it.
  const [tab, setTab] = useState<'status' | 'guide'>('status')

  const tabs = (
    <div className="flex items-center gap-1 border-b border-border">
      {([['status', 'Status'], ['guide', 'Setup guide']] as const).map(([key, label]) => (
        <button
          key={key}
          onClick={() => setTab(key)}
          className={
            'px-3.5 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ' +
            (tab === key
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground')
          }
        >
          {label}
        </button>
      ))}
    </div>
  )

  if (!a) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-32 bg-muted rounded animate-pulse" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
        </div>
      </div>
    )
  }

  if (notConnected) {
    return (
        <div className="space-y-6 max-w-3xl">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Agent</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Collection agent running in your AWS account
            </p>
          </div>

          {tabs}

          {tab === 'status' ? (
            <>
              <Card>
                <CardContent className="p-8 text-center">
                  <div className="w-14 h-14 rounded-full bg-muted/40 border border-border flex items-center justify-center mx-auto mb-4">
                    <Radio className="w-6 h-6 text-muted-foreground" />
                  </div>
                  <h2 className="text-lg font-semibold text-foreground mb-1.5">No agent connected yet</h2>
                  <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
                    Nothing is reporting from your AWS account, so there is no health,
                    no collectors and no metrics to show. Deploy the read-only agent
                    and this page fills in on its own, usually within a few minutes.
                  </p>
                </CardContent>
              </Card>

              <DeployAgentCard customerId={customerId || ''} />
            </>
          ) : (
            <>
              <DeployAgentCard customerId={customerId || ''} />
              <SetupGuide customerId={customerId || undefined} />
            </>
          )}
        </div>
    )
  }

  // Read once, guarded: the API returns collectors_enabled/regions_monitored,
  // and useAgent reshapes them, but a null here must not blank the page.
  const collectors = a.collectors ?? []
  const regions    = a.regions ?? []
  const okCollectors   = collectors.filter(c => c.status === 'ok').length
  const warnCollectors = collectors.length - okCollectors

  return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Agent</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            Collection agent running in your AWS account
          </p>
        </div>

        {tabs}

        {tab === 'guide' ? (
          <>
            <DeployAgentCard customerId={customerId || a.customer_id} />
            <SetupGuide customerId={customerId || a.customer_id} />
          </>
        ) : (
        <>
        <DeployAgentCard customerId={customerId || a.customer_id} />

        {/* Status hero */}
        <Card className={a.status === 'healthy' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}>
          <CardContent className="p-5">
            <div className="flex items-center gap-4 flex-wrap">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${
                a.status === 'healthy'
                  ? 'bg-emerald-500/20 border border-emerald-500/30'
                  : 'bg-amber-500/20 border border-amber-500/30'
              }`}>
                <Radio className={`w-7 h-7 ${a.status === 'healthy' ? 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400' : 'text-amber-500 dark:text-amber-400'}`} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xl font-bold text-foreground capitalize">{a.status}</span>
                  <span className={`w-2 h-2 rounded-full ${a.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
                </div>
                <p className="text-sm text-muted-foreground">
                  Customer <span className="text-foreground font-mono">{a.customer_id}</span> · Version {a.version} · Up {fmtCount(a.uptime_hours)}h
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="text-muted-foreground text-xs mb-0.5">Last heartbeat</p>
                <p className="font-medium text-foreground">{formatRelativeTime(a.last_heartbeat)}</p>
                <p className="text-xs text-muted-foreground mt-1">{a.collection_interval_s}s interval</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Metrics Collected',  value: fmtCount(a.metrics_collected_total), icon: Activity,    color: 'text-indigo-400' },
            { label: 'Regions Covered',    value: regions.length.toString(),                icon: Radio,       color: 'text-blue-400'   },
            { label: 'Active Collectors',  value: `${okCollectors}/${collectors.length}`,   icon: CheckCircle, color: 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400' },
            { label: 'Collection Interval',value: `${a.collection_interval_s}s`,              icon: Clock,       color: 'text-amber-500 dark:text-amber-400'  },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <s.icon className={`w-4 h-4 ${s.color}`} />
                  <span className="text-xs text-muted-foreground">{s.label}</span>
                </div>
                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Regions */}
        <Card>
          <CardContent className="p-5">
            <h3 className="font-semibold text-foreground mb-3">Regions Monitored</h3>
            <div className="flex flex-wrap gap-2">
              {regions.map(r => (
                <div key={r} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-muted/20 border border-border">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span className="text-sm font-mono text-foreground">{r}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Collectors table */}
        <Card>
          <CardContent className="p-0">
            <div className="px-5 pt-5 pb-3 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-foreground">Collectors</h3>
                <p className="text-xs text-muted-foreground mt-0.5">{collectors.length} collectors</p>
              </div>
              {warnCollectors > 0
                ? <Badge variant="warning">{warnCollectors} degraded</Badge>
                : <Badge variant="success">All healthy</Badge>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {['Collector', 'Status', 'Last Run', 'Resources', 'Metrics Sent'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {collectors.map((c, idx) => (
                    <tr key={c.name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                      <td className="px-4 py-3 font-medium text-foreground">{c.name}</td>
                      <td className="px-4 py-3">
                        {c.status === 'ok'
                          ? <Badge variant="success">ok</Badge>
                          : <Badge variant="error">{c.status}</Badge>}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatRelativeTime(c.last_run)}</td>
                      <td className="px-4 py-3 text-foreground">{c.resources ?? '—'}</td>
                      <td className="px-4 py-3 text-foreground">{c.metrics_sent ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
        </>
        )}
      </div>
  )
}
