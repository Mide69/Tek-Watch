'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { useAuth } from '@/hooks/useAuth'
import { useNetworking } from '@/hooks/useData'
import { fmtCount, fmtPercent, DASH } from '@/lib/utils'

/**
 * The page shell only ever depends on the signed-in customer id, never on
 * networking data, so it always renders — sidebar, Home link, Sign out
 * included — even when the content below throws. Before this, a null field
 * anywhere in NetworkingContent threw while this whole file's default export
 * was still being evaluated as one function call, which took the entire
 * <DashboardLayout> — chrome and all — down with it: the ErrorBoundary card
 * that replaced it had no sidebar, no Home, no Sign out, because none of
 * that had rendered yet either. Wrapping just the content in its own
 * boundary, as a separately-rendered child rather than inline JSX, means a
 * crash in the data area can no longer strand someone with no way back.
 */
export default function NetworkingPage() {
  const { customerId } = useAuth()
  return (
    <DashboardLayout customerId={customerId || undefined}>
      <ErrorBoundary>
        <NetworkingContent />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function NetworkingContent() {
  const { data } = useNetworking()

  if (!data) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-40 bg-muted rounded animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
        </div>
      </div>
    )
  }

  const { vpcs, elbs, cloudfront } = data

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Networking</h1>
        <p className="text-muted-foreground text-sm mt-0.5">
          VPC · Load Balancers · CloudFront — {vpcs.length} VPCs, {elbs.length} LBs, {cloudfront.length} distributions
        </p>
      </div>

      {/* VPCs */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">VPCs</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {vpcs.map(vpc => (
            <Card key={vpc.vpc_id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-foreground">{vpc.name}</span>
                  <Badge variant="success">{vpc.state}</Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center mb-3">
                  {[
                    ['CIDR',         vpc.cidr || DASH],
                    ['Subnets',      fmtCount(vpc.subnets)],
                    ['Route Tables', fmtCount(vpc.route_tables)],
                  ].map(([k, v]) => (
                    <div key={String(k)} className="p-2 rounded-lg bg-muted/30 border border-border">
                      <div className="text-xs text-muted-foreground">{k}</div>
                      <div className="text-sm font-semibold text-foreground mt-0.5">{v}</div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="font-mono">{vpc.vpc_id}</span>
                  <span>{vpc.region}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Load Balancers */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Load Balancers</h2>
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {['Name', 'Type', 'Scheme', 'Req/day', '5xx %', 'Latency', 'Targets'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {elbs.map((lb, idx) => (
                    <tr key={lb.name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                      <td className="px-4 py-3 font-medium text-foreground">{lb.name}</td>
                      <td className="px-4 py-3"><Badge variant="info">{lb.type}</Badge></td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{lb.scheme}</td>
                      <td className="px-4 py-3 text-foreground">{fmtCount(lb.request_count)}</td>
                      <td className="px-4 py-3">
                        <span className={(lb.error_5xx ?? 0) > 1 ? 'text-red-400 font-semibold' : 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400'}>
                          {fmtPercent(lb.error_5xx, 2)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-foreground">{lb.latency_ms == null ? DASH : `${lb.latency_ms} ms`}</td>
                      <td className="px-4 py-3">
                        <span className={
                          lb.healthy != null && lb.targets != null && lb.healthy < lb.targets
                            ? 'text-red-500 dark:text-red-400'
                            : 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400'
                        }>
                          {fmtCount(lb.healthy)}
                        </span>
                        <span className="text-muted-foreground text-xs">/{fmtCount(lb.targets)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* CloudFront */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">CloudFront Distributions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {cloudfront.map(cf => (
            <Card key={cf.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="font-semibold text-foreground">{cf.domain}</span>
                    <p className="text-xs font-mono text-muted-foreground mt-0.5">{cf.id}</p>
                  </div>
                  <Badge variant="success">{cf.status}</Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  {[
                    ['Req/day',   fmtCount(cf.requests_day)],
                    ['Error %',   fmtPercent(cf.error_rate, 2)],
                    ['Cache Hit', fmtPercent(cf.cache_hit)],
                  ].map(([k, v]) => (
                    <div key={String(k)} className="p-2 rounded-lg bg-muted/30 border border-border">
                      <div className="text-xs text-muted-foreground">{k}</div>
                      <div className="text-sm font-semibold text-foreground mt-0.5">{v}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
