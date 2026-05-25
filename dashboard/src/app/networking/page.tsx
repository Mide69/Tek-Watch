'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { useAuth } from '@/hooks/useAuth'
import { useNetworking } from '@/hooks/useData'

export default function NetworkingPage() {
  const { customerId }       = useAuth()
  const { data, isLoading }  = useNetworking()

  if (isLoading || !data) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-40 bg-white/[0.06] rounded animate-pulse" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const { vpcs, elbs, cloudfront } = data

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Networking</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            VPC · Load Balancers · CloudFront — {vpcs.length} VPCs, {elbs.length} LBs, {cloudfront.length} distributions
          </p>
        </div>

        {/* VPCs */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">VPCs</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {vpcs.map(vpc => (
              <Card key={vpc.vpc_id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold text-white">{vpc.name}</span>
                    <Badge variant="success">{vpc.state}</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center mb-3">
                    {[
                      ['CIDR',         vpc.cidr],
                      ['Subnets',      vpc.subnets],
                      ['Route Tables', vpc.route_tables],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                        <div className="text-xs text-slate-500">{k}</div>
                        <div className="text-sm font-semibold text-slate-200 mt-0.5">{v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-500">
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
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Load Balancers</h2>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Name', 'Type', 'Scheme', 'Req/day', '5xx %', 'Latency', 'Targets'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {elbs.map((lb, idx) => (
                      <tr key={lb.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white">{lb.name}</td>
                        <td className="px-4 py-3"><Badge variant="info">{lb.type}</Badge></td>
                        <td className="px-4 py-3 text-xs text-slate-400">{lb.scheme}</td>
                        <td className="px-4 py-3 text-slate-300">{lb.request_count.toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <span className={lb.error_5xx > 1 ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
                            {lb.error_5xx.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{lb.latency_ms} ms</td>
                        <td className="px-4 py-3">
                          <span className={lb.healthy < lb.targets ? 'text-red-400' : 'text-emerald-400'}>
                            {lb.healthy}
                          </span>
                          <span className="text-slate-500 text-xs">/{lb.targets}</span>
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
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">CloudFront Distributions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cloudfront.map(cf => (
              <Card key={cf.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <span className="font-semibold text-white">{cf.domain}</span>
                      <p className="text-xs font-mono text-slate-500 mt-0.5">{cf.id}</p>
                    </div>
                    <Badge variant="success">{cf.status}</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    {[
                      ['Req/day',   cf.requests_day.toLocaleString()],
                      ['Error %',   `${cf.error_rate.toFixed(2)}%`],
                      ['Cache Hit', `${cf.cache_hit.toFixed(1)}%`],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                        <div className="text-xs text-slate-500">{k}</div>
                        <div className="text-sm font-semibold text-slate-200 mt-0.5">{v}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </div>
    </DashboardLayout>
  )
}
