'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Database, Table2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_RDS, MOCK_DYNAMODB } from '@/lib/mockData'

function PctBar({ value, max, warn = 70, crit = 85 }: { value: number; max: number; warn?: number; crit?: number }) {
  const pct = Math.min((value / max) * 100, 100)
  const col = pct >= crit ? 'bg-red-500' : pct >= warn ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div className={`h-full ${col} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium w-16 text-right ${pct >= crit ? 'text-red-400' : pct >= warn ? 'text-amber-400' : 'text-slate-300'}`}>
        {value}/{max}
      </span>
    </div>
  )
}

export default function DatabasesPage() {
  const { loading: authLoading } = useAuth()
  const [tab, setTab] = useState<'rds' | 'ddb'>('rds')

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
          <h1 className="text-2xl font-bold text-white">Databases</h1>
          <p className="text-slate-400 text-sm mt-0.5">RDS · DynamoDB — {MOCK_RDS.length} RDS instances, {MOCK_DYNAMODB.length} tables</p>
        </div>

        <div className="flex gap-1 p-1 bg-white/[0.03] border border-white/[0.06] rounded-xl w-fit">
          {[{ key: 'rds', label: 'RDS / Aurora', icon: Database }, { key: 'ddb', label: 'DynamoDB', icon: Table2 }].map(t => (
            <button key={t.key} onClick={() => setTab(t.key as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}>
              <t.icon className="w-4 h-4" />{t.label}
            </button>
          ))}
        </div>

        {tab === 'rds' && (
          <div className="space-y-4">
            {MOCK_RDS.map(db => (
              <Card key={db.id}>
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-semibold text-white">{db.id}</span>
                        {db.multi_az && <Badge variant="info">Multi-AZ</Badge>}
                        <Badge variant="success">{db.status}</Badge>
                      </div>
                      <p className="text-xs text-slate-500">{db.engine} · {db.class} · {db.region}</p>
                    </div>
                    <div className="text-right">
                      <div className={`text-2xl font-bold ${db.cpu > 70 ? 'text-amber-400' : 'text-white'}`}>{db.cpu.toFixed(1)}%</div>
                      <div className="text-xs text-slate-500">CPU</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Connections</p>
                      <PctBar value={db.connections} max={db.max_connections} warn={70} crit={85} />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1.5">Storage</p>
                      <span className="text-sm font-medium text-slate-300">{db.storage_gb} GB</span>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1.5">Read Latency</p>
                      <span className="text-sm font-medium text-slate-300">{db.read_latency_ms} ms</span>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1.5">IOPS</p>
                      <span className="text-sm font-medium text-slate-300">{db.iops.toLocaleString()}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {tab === 'ddb' && (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      {['Table', 'Status', 'Items', 'Size', 'Read Cap', 'Write Cap', 'Throttles'].map(h => (
                        <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_DYNAMODB.map((t, idx) => (
                      <tr key={t.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                        <td className="px-4 py-3 font-medium text-white">{t.name}</td>
                        <td className="px-4 py-3"><Badge variant="success">{t.status}</Badge></td>
                        <td className="px-4 py-3 text-slate-300">{t.item_count.toLocaleString()}</td>
                        <td className="px-4 py-3 text-slate-300">{t.size_gb.toFixed(1)} GB</td>
                        <td className="px-4 py-3 text-slate-300">{t.read_capacity}</td>
                        <td className="px-4 py-3 text-slate-300">{t.write_capacity}</td>
                        <td className="px-4 py-3">
                          {(t.throttled_reads + t.throttled_writes) > 0
                            ? <Badge variant="warning">{t.throttled_reads + t.throttled_writes}</Badge>
                            : <span className="text-xs text-emerald-400">0</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  )
}
