'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_VPCS, MOCK_ELBS, MOCK_CLOUDFRONT } from '@/lib/mockData'

export default function NetworkingPage() {
  const { loading: authLoading } = useAuth()

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
          <h1 className="text-2xl font-bold text-white">Networking</h1>
          <p className="text-slate-400 text-sm mt-0.5">VPC · Load Balancers · CloudFront</p>
        </div>

        {/* VPCs */}
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">VPCs</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {MOCK_VPCS.map(vpc => (
              <Card key={vpc.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold text-white">{vpc.name}</span>
                    <Badge variant="success">{vpc.state}</Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-center">
                    {[
                      ['CIDR', vpc.cidr],
                      ['Subnets', vpc.subnets],
                      ['NAT GWs', vpc.nat_gateways],
                    ].map(([k, v]) => (
                      <div key={String(k)} className="p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                        <div className="text-xs text-slate-500">{k}</div>
                        <div className="text-sm font-semibold text-slate-200 mt-0.5">{v}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-3 font-mono">{vpc.id} · {vpc.region}</p>
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
                      {['Name', 'Type', 'Scheme', 'Req/min', '5xx %', 'Latency', 'Targets'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_ELBS.map((lb, idx) => (
                      <tr key={lb.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white">{lb.name}</td>
                        <td className="px-4 py-3"><Badge variant="info">{lb.type}</Badge></td>
                        <td className="px-4 py-3 text-xs text-slate-400">{lb.scheme}</td>
                        <td className="px-4 py-3 text-slate-300">{lb.requests_pm.toLocaleString()}</td>
                        <td className="px-4 py-3">
                          <span className={lb.req_5xx_pct > 1 ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
                            {lb.req_5xx_pct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{lb.latency_ms} ms</td>
                        <td className="px-4 py-3">
                          <span className={lb.healthy_targets < lb.active_targets ? 'text-red-400' : 'text-emerald-400'}>
                            {lb.healthy_targets}
                          </span>
                          <span className="text-slate-500 text-xs">/{lb.active_targets}</span>
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
            {MOCK_CLOUDFRONT.map(cf => (
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
                      ['Req/min', cf.requests_pm.toLocaleString()],
                      ['Error %', `${cf.error_pct.toFixed(2)}%`],
                      ['Cache Hit', `${cf.cache_hit_pct.toFixed(1)}%`],
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
