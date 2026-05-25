'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { CardSkeleton } from '@/components/ui/Skeleton'
import { HardDrive, Lock, Unlock, Shield } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useStorage } from '@/hooks/useData'

function fmtSize(bytes: number) {
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`
  if (bytes >= 1e9)  return `${(bytes / 1e9).toFixed(1)} GB`
  return `${(bytes / 1e6).toFixed(1)} MB`
}

export default function StoragePage() {
  const { customerId }      = useAuth()
  const { data: buckets, isLoading } = useStorage()

  if (isLoading || !buckets) {
    return (
      <DashboardLayout customerId={customerId || undefined}>
        <div className="space-y-6">
          <div className="h-8 w-32 bg-white/[0.06] rounded animate-pulse" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[0,1,2,3].map(i => <CardSkeleton key={i} />)}
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const totalBytes = buckets.reduce((s, b) => s + b.size_bytes, 0)
  const totalObjs  = buckets.reduce((s, b) => s + b.object_count, 0)
  const encrypted  = buckets.filter(b => !!b.encryption).length
  const versioned  = buckets.filter(b => b.versioning).length
  const publicBkts = buckets.filter(b => !b.public_access_blocked).length

  return (
    <DashboardLayout customerId={customerId || undefined}>
      <div className="space-y-6 animate-fade-in">
        <div>
          <h1 className="text-2xl font-bold text-white">Storage</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            S3 — {buckets.length} buckets across {[...new Set(buckets.map(b => b.region))].length} regions
          </p>
        </div>

        {/* Summary tiles */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Storage',   value: fmtSize(totalBytes),              icon: HardDrive, color: 'text-blue-400',    bg: 'bg-blue-500/10 border-blue-500/20'    },
            { label: 'Total Objects',   value: totalObjs.toLocaleString(),        icon: HardDrive, color: 'text-indigo-400',  bg: 'bg-indigo-500/10 border-indigo-500/20' },
            { label: 'Encrypted',       value: `${encrypted}/${buckets.length}`,  icon: Lock,      color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
            { label: 'Public Buckets',  value: publicBkts.toString(),             icon: publicBkts > 0 ? Unlock : Shield, color: publicBkts > 0 ? 'text-red-400' : 'text-emerald-400', bg: publicBkts > 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20' },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-400">{s.label}</span>
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
                  <tr className="border-b border-white/[0.06]">
                    {['Bucket', 'Region', 'Size', 'Objects', 'Cost MTD', 'Versioning', 'Encryption', 'Public'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...buckets].sort((a, b) => b.size_bytes - a.size_bytes).map((b, idx) => (
                    <tr key={b.bucket_name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                      <td className="px-4 py-3 font-medium text-white">{b.bucket_name}</td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-400">{b.region}</td>
                      <td className="px-4 py-3 text-slate-300">{fmtSize(b.size_bytes)}</td>
                      <td className="px-4 py-3 text-slate-300">{b.object_count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-slate-300">${b.cost_mtd.toFixed(2)}</td>
                      <td className="px-4 py-3">
                        {b.versioning
                          ? <Badge variant="success">enabled</Badge>
                          : <Badge variant="default">disabled</Badge>}
                      </td>
                      <td className="px-4 py-3">
                        {b.encryption
                          ? <div className="flex items-center gap-1.5 text-emerald-400 text-xs"><Lock className="w-3 h-3" />{b.encryption}</div>
                          : <div className="flex items-center gap-1.5 text-red-400 text-xs"><Unlock className="w-3 h-3" />None</div>}
                      </td>
                      <td className="px-4 py-3">
                        {!b.public_access_blocked
                          ? <Badge variant="error">Public</Badge>
                          : <span className="text-xs text-emerald-400">Blocked</span>}
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
