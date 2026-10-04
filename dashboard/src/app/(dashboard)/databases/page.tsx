'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { TableSkeleton } from '@/components/ui/Skeleton'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Sparkline } from '@/components/ui/MiniChart'
import { Database, Table2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useDashboard, TIME_RANGE_LABELS } from '@/contexts/DashboardContext'
import { useRDS, useDynamoDB } from '@/hooks/useData'
import { fmtCount, fmtNum, fmtPercent, DASH } from '@/lib/utils'

function PctBar({ value, warn = 70, crit = 85 }: { value: number | null; warn?: number; crit?: number }) {
  // RDS connections are rendered as a percentage of a fixed ceiling — the
  // metric itself is a count that can be null when the agent has not
  // collected it yet, and value.toFixed(1) on null took the RDS section down.
  if (value == null) {
    return <span className="text-xs text-muted-foreground">{DASH}</span>
  }
  const col = value >= crit ? 'bg-red-500' : value >= warn ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className={`h-full ${col} rounded-full`} style={{ width: `${Math.min(value, 100)}%` }} />
      </div>
      <span className={`text-xs font-medium w-10 text-right ${value >= crit ? 'text-red-500 dark:text-red-400' : value >= warn ? 'text-amber-500 dark:text-amber-400' : 'text-foreground'}`}>
        {value.toFixed(1)}%
      </span>
    </div>
  )
}

// The shell — sidebar, Home, Sign out — depends only on who is signed in,
// never on RDS/DynamoDB data, so it renders even when the content below
// throws. See the identical note in networking/page.tsx for why this split
// exists.
export default function DatabasesPage() {
  const { customerId } = useAuth()
  return (
    <DashboardLayout customerId={customerId || undefined}>
      <ErrorBoundary>
        <DatabasesContent />
      </ErrorBoundary>
    </DashboardLayout>
  )
}

function DatabasesContent() {
  const { timeRange }  = useDashboard()
  const [tab, setTab]  = useState<'rds' | 'ddb'>('rds')

  const { data: rds, isLoading: rdsLoading }   = useRDS()
  const { data: ddb, isLoading: ddbLoading }   = useDynamoDB()

  const isLoading = (tab === 'rds' && rdsLoading) || (tab === 'ddb' && ddbLoading)

  return (
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Databases</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            RDS · DynamoDB — {(rds || []).length} RDS instances, {(ddb || []).length} tables · {TIME_RANGE_LABELS[timeRange]}
          </p>
        </div>

        <div className="flex gap-1 p-1 bg-muted/30 border border-border rounded-xl w-fit">
          {[
            { key: 'rds', label: 'RDS / Aurora', icon: Database },
            { key: 'ddb', label: 'DynamoDB',     icon: Table2  },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key as 'rds' | 'ddb')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t.key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-accent'
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
                            <span className="font-semibold text-foreground">{db.db_identifier}</span>
                            {db.multi_az && <Badge variant="info">Multi-AZ</Badge>}
                            <Badge variant="success">{db.status}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{db.engine} · {db.instance_class} · {db.region}</p>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold ${(db.cpu ?? 0) > 70 ? 'text-amber-500 dark:text-amber-400' : 'text-foreground'}`}>
                            {fmtPercent(db.cpu)}
                          </div>
                          <div className="text-xs text-muted-foreground">CPU</div>
                        </div>
                      </div>

                      {/* Metrics row */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1.5">Connections</p>
                          <PctBar value={db.connections == null ? null : Math.min((db.connections / 210) * 100, 100)} />
                          <p className="text-xs text-muted-foreground mt-1">{fmtCount(db.connections)} active</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1.5">Free Storage</p>
                          <span className="text-sm font-medium text-foreground">{fmtNum(db.free_storage_gb, 0)} GB</span>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1.5">Read IOPS</p>
                          <span className="text-sm font-medium text-foreground">{fmtCount(db.read_iops)}</span>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1.5">Write IOPS</p>
                          <span className="text-sm font-medium text-foreground">{fmtCount(db.write_iops)}</span>
                        </div>
                      </div>

                      {/* CPU sparkline */}
                      {db.metrics?.cpu && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">CPU over {TIME_RANGE_LABELS[timeRange]}</p>
                          <Sparkline
                            data={db.metrics.cpu.map((p: { value: number }) => ({ value: p.value }))}
                            color={(db.cpu ?? 0) > 70 ? '#fbbf24' : '#1f8c9e'}
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
                        <tr className="border-b border-border">
                          {['Table', 'Status', 'Items', 'Size (GB)', 'Read Cap', 'Write Cap', 'Consumed R', 'Consumed W', 'Throttles'].map(h => (
                            <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(ddb || []).map((t, idx) => (
                          <tr key={t.table_name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                            <td className="px-4 py-3 font-medium text-foreground">{t.table_name}</td>
                            <td className="px-4 py-3"><Badge variant="success">{t.status}</Badge></td>
                            <td className="px-4 py-3 text-foreground">{fmtCount(t.item_count)}</td>
                            <td className="px-4 py-3 text-foreground">{t.size_bytes == null ? DASH : (t.size_bytes / 1e9).toFixed(2)}</td>
                            <td className="px-4 py-3 text-foreground">{fmtCount(t.read_capacity)}</td>
                            <td className="px-4 py-3 text-foreground">{fmtCount(t.write_capacity)}</td>
                            <td className="px-4 py-3 text-foreground">{fmtNum(t.consumed_read)}</td>
                            <td className="px-4 py-3 text-foreground">{fmtNum(t.consumed_write)}</td>
                            <td className="px-4 py-3">
                              {(() => {
                                const throttled = (t.throttled_reads ?? 0) + (t.throttled_writes ?? 0)
                                return throttled > 0
                                  ? <Badge variant="warning">{throttled}</Badge>
                                  : <span className="text-xs text-emerald-600 dark:text-emerald-400">0</span>
                              })()}
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
  )
}
