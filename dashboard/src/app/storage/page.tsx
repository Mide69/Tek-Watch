'use client'

import DashboardLayout from '@/components/layout/DashboardLayout'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { HardDrive, Lock, Unlock } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { MOCK_S3 } from '@/lib/mockData'
import { formatBytes } from '@/lib/utils'

export default function StoragePage() {
  const { loading: authLoading } = useAuth()

  const totalGb   = MOCK_S3.reduce((s, b) => s + b.size_gb, 0)
  const totalObjs = MOCK_S3.reduce((s, b) => s + b.object_count, 0)
  const encrypted = MOCK_S3.filter(b => b.encrypted).length
  const versioned = MOCK_S3.filter(b => b.versioning).length

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
          <h1 className="text-2xl font-bold text-white">Storage</h1>
          <p className="text-slate-400 text-sm mt-0.5">S3 — {MOCK_S3.length} buckets across {[...new Set(MOCK_S3.map(b => b.region))].length} regions</p>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Storage',   value: `${totalGb.toFixed(1)} GB`, icon: HardDrive, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
            { label: 'Total Objects',   value: totalObjs.toLocaleString(), icon: HardDrive, color: 'text-indigo-400', bg: 'bg-indigo-500/10 border-indigo-500/20' },
            { label: 'Encrypted',       value: `${encrypted}/${MOCK_S3.length}`, icon: Lock, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
            { label: 'Versioned',       value: `${versioned}/${MOCK_S3.length}`, icon: Lock, color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/20' },
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
                    {['Bucket', 'Region', 'Size', 'Objects', 'Versioning', 'Encrypted'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-medium text-slate-500 whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {MOCK_S3.sort((a, b) => b.size_gb - a.size_gb).map((b, idx) => (
                    <tr key={b.name} className={`border-b border-white/[0.04] hover:bg-white/[0.02] ${idx % 2 ? 'bg-white/[0.01]' : ''}`}>
                      <td className="px-4 py-3 font-medium text-white">{b.name}</td>
                      <td className="px-4 py-3 text-xs font-mono text-slate-400">{b.region}</td>
                      <td className="px-4 py-3 text-slate-300">{b.size_gb.toFixed(1)} GB</td>
                      <td className="px-4 py-3 text-slate-300">{b.object_count.toLocaleString()}</td>
                      <td className="px-4 py-3">
                        {b.versioning
                          ? <Badge variant="success">enabled</Badge>
                          : <Badge variant="default">disabled</Badge>}
                      </td>
                      <td className="px-4 py-3">
                        {b.encrypted
                          ? <div className="flex items-center gap-1.5 text-emerald-400 text-xs"><Lock className="w-3 h-3" />Yes</div>
                          : <div className="flex items-center gap-1.5 text-red-400 text-xs"><Unlock className="w-3 h-3" />No</div>}
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
