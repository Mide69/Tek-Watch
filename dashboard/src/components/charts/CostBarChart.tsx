'use client'

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts'
import { format, parseISO } from 'date-fns'
import { formatCurrency } from '@/lib/utils'

interface CostDataPoint { time: string; cost: number }
interface CostBarChartProps { data: CostDataPoint[]; height?: number; loading?: boolean }

const GRID    = 'rgba(255,255,255,0.05)'
const TICK    = '#64748b'
const TIP_STY = { borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: '#0e1525', fontSize: 12, color: '#e2eaf4' }

export default function CostBarChart({ data, height = 240, loading = false }: CostBarChartProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-white/[0.02] animate-pulse" style={{ height }}>
        <p className="text-sm text-slate-500">Loading…</p>
      </div>
    )
  }
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed border-white/[0.08]" style={{ height }}>
        <p className="text-sm text-slate-500">No data</p>
      </div>
    )
  }

  const formatted = data.map(d => ({
    ...d,
    _day: (() => { try { return format(parseISO(d.time), 'MMM d') } catch { return d.time } })(),
  }))
  const maxCost = Math.max(...formatted.map(d => d.cost))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={formatted} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="_day" tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false}
          interval={Math.floor(formatted.length / 8)} />
        <YAxis tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false}
          tickFormatter={v => `$${v}`} width={48} />
        <Tooltip formatter={(v: number) => [formatCurrency(v), 'Cost']} contentStyle={TIP_STY} />
        <Bar dataKey="cost" radius={[3, 3, 0, 0]}>
          {formatted.map((e, i) => (
            <Cell key={i} fill={e.cost === maxCost ? '#f97316' : '#6366f1'} fillOpacity={e.cost === maxCost ? 1 : 0.65} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
