'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { HardDrive, Lock, Unlock, Shield } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useStorage } from '@/hooks/useData'

// A metric the agent could not collect is null, not zero, so every one of
// these has to survive a missing value. The page used to read
// b.object_count.toLocaleString() straight off the row and took the whole
// Storage route down with "Cannot read properties of undefined" the first
// time the API returned a shape it did not expect.
const DASH = '—'

function fmtSize(bytes: number | null | undefined) {
  if (bytes == null) return DASH
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`
  if (bytes >= 1e9)  return `${(bytes / 1e9).toFixed(1)} GB`
  return `${(bytes / 1e6).toFixed(1)} MB`
}

function fmtCount(n: number | null | undefined) {
  return n == null ? DASH : n.toLocaleString()
}

function fmtCost(n: number | null | undefined) {
  return n == null ? DASH : `$${n.toFixed(2)}`
}

export default function StoragePage() {
  const { customerId }      = useAuth()
  const { data: buckets } = useStorage()

  if (!buckets) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-32 bg-muted rounded animate-pulse" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const totalBytes = buckets.reduce((s, b) => s + (b.size_bytes ?? 0), 0)
  const totalObjs  = buckets.reduce((s, b) => s + (b.object_count ?? 0), 0)
  const encrypted  = buckets.filter(b => !!b.encryption).length
  const versioned  = buckets.filter(b => b.versioning === true).length
  // Only buckets we actually determined to be reachable. public_access_blocked
  // is null when the agent could not read the setting, and counting null as
  // "not blocked" labelled every bucket in the account Public.
  const publicBkts = buckets.filter(b => b.public_access_blocked === false).length

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Storage</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            S3 — {buckets.length} buckets across {[...new Set(buckets.map(b => b.region))].length} regions
          </p>
        </div>

        {/* Summary tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Storage',   value: fmtSize(totalBytes),              icon: HardDrive, color: 'text-blue-400',    bg: 'bg-blue-500/10 border-blue-500/20'    },
            { label: 'Total Objects',   value: fmtCount(totalObjs),        icon: HardDrive, color: 'text-indigo-400',  bg: 'bg-indigo-500/10 border-indigo-500/20' },
            { label: 'Encrypted',       value: `${encrypted}/${buckets.length}`,  icon: Lock,      color: 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
            { label: 'Public Buckets',  value: publicBkts.toString(),             icon: publicBkts > 0 ? Unlock : Shield, color: publicBkts > 0 ? 'text-red-500 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-600 dark:text-emerald-400', bg: publicBkts > 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20' },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">{s.label}</span>
                  <div className={`w-7 h-7 rounded-lg border flex items-center justify-center ${s.bg}`}>
                    <s.icon className={`w-3.5 h-3.5 ${s.color}`} />
                  </div>
                </div>
                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Bucket table */}
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {['Bucket', 'Region', 'Size', 'Objects', 'Cost MTD', 'Versioning', 'Encryption', 'Public'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...buckets].sort((a, b) => (b.size_bytes ?? 0) - (a.size_bytes ?? 0)).map((b, idx) => (
                    <tr key={b.bucket_name} className={`border-b border-border/40 hover:bg-muted/30 ${idx % 2 ? 'bg-muted/10' : ''}`}>
                      <td className="px-4 py-3 font-medium text-foreground">{b.bucket_name}</td>
                      <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{b.region}</td>
                      <td className="px-4 py-3 text-foreground">{fmtSize(b.size_bytes)}</td>
                      <td className="px-4 py-3 text-foreground">{fmtCount(b.object_count)}</td>
                      <td className="px-4 py-3 text-foreground">{fmtCost(b.cost_mtd)}</td>
                      <td className="px-4 py-3">
                        {b.versioning == null
                          ? <span className="text-xs text-muted-foreground">{DASH}</span>
                          : b.versioning
                            ? <Badge variant="success">enabled</Badge>
                            : <Badge variant="default">disabled</Badge>}
                      </td>
                      <td className="px-4 py-3">
                        {b.encryption
                          ? <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs"><Lock className="w-3 h-3" />{b.encryption}</div>
                          : <div className="flex items-center gap-1.5 text-red-400 text-xs"><Unlock className="w-3 h-3" />None</div>}
                      </td>
                      <td className="px-4 py-3">
                        {b.public_access_blocked == null
                          ? <span className="text-xs text-muted-foreground" title="The agent could not read this bucket's public access settings">Unknown</span>
                          : b.public_access_blocked
                            ? <span className="text-xs text-emerald-600 dark:text-emerald-400">Blocked</span>
                            : <Badge variant="error">Public</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
