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

// Theme tokens, not fixed slate. These were written when the product was dark
// only: on the light theme the grid was white on white and the tooltip was a
// dark slab in the middle of a pale page.
const GRID   = 'hsl(var(--border))'
const TICK   = 'hsl(var(--muted-foreground))'
const TOOLTIP_STYLE = {
  borderRadius: 8,
  border: '1px solid hsl(var(--border))',
  background: 'hsl(var(--popover))',
  fontSize: 12,
  color: 'hsl(var(--popover-foreground))',
}

export default function TimeSeriesChart({
  data, dataKey = 'value', color = '#6366f1', unit = '',
  height = 240, type = 'area', loading = false, formatValue,
}: TimeSeriesChartProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-muted/30 animate-pulse" style={{ height }}>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed border-border" style={{ height }}>
        <p className="text-sm text-muted-foreground">No data</p>
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
