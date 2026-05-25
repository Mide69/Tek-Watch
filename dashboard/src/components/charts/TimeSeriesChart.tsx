'use client'

import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, AreaChart, Area,
} from 'recharts'
import { format, parseISO } from 'date-fns'

export interface TimeSeriesPoint {
  time: string
  value: number
  [key: string]: string | number
}

interface TimeSeriesChartProps {
  data: TimeSeriesPoint[]
  dataKey?: string
  color?: string
  unit?: string
  height?: number
  type?: 'line' | 'area'
  loading?: boolean
  formatValue?: (v: number) => string
}

function fmt(t: string) {
  try { return format(parseISO(t), 'HH:mm') } catch { return t }
}

const GRID   = 'rgba(255,255,255,0.05)'
const TICK   = '#64748b'
const TOOLTIP_STYLE = { borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: '#0e1525', fontSize: 12, color: '#e2eaf4' }

export default function TimeSeriesChart({
  data, dataKey = 'value', color = '#6366f1', unit = '',
  height = 240, type = 'area', loading = false, formatValue,
}: TimeSeriesChartProps) {
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

  const points = data.map(d => ({ ...d, _t: fmt(d.time) }))
  const tipFmt = (v: number) => formatValue ? formatValue(v) : `${v.toFixed(2)}${unit ? ' ' + unit : ''}`

  if (type === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id={`g-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={color} stopOpacity={0.2} />
              <stop offset="95%" stopColor={color} stopOpacity={0}   />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis dataKey="_t" tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false}
            tickFormatter={v => formatValue ? formatValue(v) : `${v}${unit}`} width={44} />
          <Tooltip formatter={tipFmt} contentStyle={TOOLTIP_STYLE} />
          <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2}
            fill={`url(#g-${dataKey})`} dot={false} activeDot={{ r: 3, strokeWidth: 0 }} />
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis dataKey="_t" tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 11, fill: TICK }} tickLine={false} axisLine={false}
          tickFormatter={v => formatValue ? formatValue(v) : `${v}${unit}`} width={44} />
        <Tooltip formatter={tipFmt} contentStyle={TOOLTIP_STYLE} />
        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2}
          dot={false} activeDot={{ r: 3, strokeWidth: 0 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
