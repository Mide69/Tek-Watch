'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { Sparkline } from '@/components/ui/MiniChart'
import { Database, Table2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useRDS, useDynamoDB } from '@/hooks/useData'

function PctBar({ value, warn = 70, crit = 85 }: { value: number; warn?: number; crit?: number }) {
  const col = value >= crit ? 'bg-red-500' : value >= warn ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
        <div className={`h-full ${col} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className={`text-xs font-medium w-10 text-right ${value >= crit ? 'text-red-400' : value >= warn ? 'text-amber-400' : 'text-slate-300'}`}>
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

export default function DatabasesPage() {
  const { customerId } = useAuth()
  const { timeRange }  = useDashboard()
  const [tab, setTab]  = useState<'rds' | 'ddb'>('rds')

  const { data: rds, isLoading: rdsLoading }   = useRDS()
  const { data: ddb, isLoading: ddbLoading }   = useDynamoDB()

  const isLoading = (tab === 'rds' && rdsLoading) || (tab === 'ddb' && ddbLoading)

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Databases</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            RDS · DynamoDB — {(rds || []).length} RDS instances, {(ddb || []).length} tables · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        <div className="flex gap-1 p-1 bg-white/[0.03] border border-white/[0.06] rounded-xl w-fit">
          {[
            { key: 'rds', label: 'RDS / Aurora', icon: Database },
            { key: 'ddb', label: 'DynamoDB',     icon: Table2  },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key as 'rds' | 'ddb')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}>
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <Card><CardContent className="p-6"><TableSkeleton rows={4} cols={5} /></CardContent></Card>
        ) : (
          <>
            {/* RDS */}
            {tab === 'rds' && (
              <div className="space-y-4">
                {(rds || []).map(db => (
                  <Card key={db.db_identifier}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
                        <div>
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <span className="font-semibold text-white">{db.db_identifier}</span>
                            {db.multi_az && <Badge variant="info">Multi-AZ</Badge>}
                            <Badge variant="success">{db.status}</Badge>
                          </div>
                          <p className="text-xs text-slate-500">{db.engine} · {db.instance_class} · {db.region}</p>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold ${db.cpu > 70 ? 'text-amber-400' : 'text-white'}`}>
                            {db.cpu.toFixed(1)}%
                          </div>
                          <div className="text-xs text-slate-500">CPU</div>
                        </div>
                      </div>

                      {/* Metrics row */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-slate-500 mb-1.5">Connections</p>
                          <PctBar value={Math.min((db.connections / 210) * 100, 100)} />
                          <p className="text-xs text-slate-500 mt-1">{db.connections} active</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1.5">Free Storage</p>
                          <span className="text-sm font-medium text-slate-300">{db.free_storage_gb.toFixed(0)} GB</span>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1.5">Read IOPS</p>
                          <span className="text-sm font-medium text-slate-300">{db.read_iops.toLocaleString()}</span>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 mb-1.5">Write IOPS</p>
                          <span className="text-sm font-medium text-slate-300">{db.write_iops.toLocaleString()}</span>
                        </div>
                      </div>

                      {/* CPU sparkline */}
                      {db.metrics?.cpu && (
                        <div>
                          <p className="text-xs text-slate-500 mb-1">CPU over {TIME_RANGE_LABELS[timeRange]}</p>
                          <Sparkline
                            data={db.metrics.cpu.map((p: { value: number }) => ({ value: p.value }))}
                            color={db.cpu > 70 ? '#fbbf24' : '#6366f1'}
                            height={40}
                          />
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* DynamoDB */}
            {tab === 'ddb' && (
              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/[0.06]">
                          {['Table', 'Status', 'Items', 'Size (GB)', 'Read Cap', 'Write Cap', 'Consumed R', 'Consumed W', 'Throttles'].map(h => (
                            <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(ddb || []).map((t, idx) => (
                          <tr key={t.table_name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                            <td className="px-4 py-3 font-medium text-white">{t.table_name}</td>
                            <td className="px-4 py-3"><Badge variant="success">{t.status}</Badge></td>
                            <td className="px-4 py-3 text-slate-300">{t.item_count.toLocaleString()}</td>
                            <td className="px-4 py-3 text-slate-300">{(t.size_bytes / 1e9).toFixed(2)}</td>
                            <td className="px-4 py-3 text-slate-300">{t.read_capacity}</td>
                            <td className="px-4 py-3 text-slate-300">{t.write_capacity}</td>
                            <td className="px-4 py-3 text-slate-300">{t.consumed_read.toFixed(1)}</td>
                            <td className="px-4 py-3 text-slate-300">{t.consumed_write.toFixed(1)}</td>
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
          </>
        )}
      </div>
    </DashboardLayout>
  )
}
