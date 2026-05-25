'use client'

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts'
import { formatCurrency } from '@/lib/utils'

interface ServiceCost { aws_service: string; mtd_cost: number }
interface CostDonutChartProps { data: ServiceCost[]; height?: number; loading?: boolean }

const COLORS = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#f97316','#ec4899','#3b82f6','#14b8a6']
const TIP_STY = { borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: '#0e1525', fontSize: 12, color: '#e2eaf4' }

export default function CostDonutChart({ data, height = 280, loading = false }: CostDonutChartProps) {
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

  const sorted = [...data].sort((a, b) => b.mtd_cost - a.mtd_cost)
  const top = sorted.slice(0, 8)
  const other = sorted.slice(8).reduce((s, d) => s + d.mtd_cost, 0)
  const chartData = other > 0 ? [...top, { aws_service: 'Other', mtd_cost: other }] : top

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={chartData} cx="50%" cy="44%" innerRadius="52%" outerRadius="72%"
          dataKey="mtd_cost" nameKey="aws_service" paddingAngle={2}>
          {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={(v: number) => [formatCurrency(v), 'Cost']} contentStyle={TIP_STY} />
        <Legend iconType="circle" iconSize={8}
          formatter={v => <span style={{ fontSize: 11, color: '#94a3b8' }}>{v}</span>} />
      </PieChart>
    </ResponsiveContainer>
  )
}
