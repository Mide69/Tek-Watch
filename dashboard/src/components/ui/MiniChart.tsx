/** Tiny SVG charts — no Recharts, no ResizeObserver, no renderer issues */

interface SparkPoint { value: number }

export function Sparkline({
  data,
  color = '#6366f1',
  height = 36,
  filled = true,
}: {
  data: SparkPoint[]
  color?: string
  height?: number
  filled?: boolean
}) {
  if (!data || data.length < 2) return null
  const W = 200
  const H = height
  const vals = data.map(d => d.value)
  const min = Math.min(...vals)
  const max = Math.max(...vals) || 1
  const range = max - min || 1

  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * W
    const y = H - 4 - ((v - min) / range) * (H - 8) + 2
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const polyline = pts.join(' ')
  const area     = `0,${H} ${polyline} ${W},${H}`
  const gradId   = `sg-${color.replace(/[^a-z0-9]/gi, '')}`

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      width="100%"
      height={height}
      style={{ display: 'block' }}
    >
      {filled && (
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor={color} stopOpacity={0.22} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
      )}
      {filled && <polygon points={area} fill={`url(#${gradId})`} />}
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** Days either side of a point that the trend line averages over. */
export function trendWindow(count: number): number {
  return Math.max(3, Math.min(7, Math.round(count / 5)))
}

/**
 * A centred moving average.
 *
 * Daily cloud spend is spiky: weekends drop, a backup job doubles a Tuesday.
 * Reading a run of bars, people see the spikes and miss the direction, which
 * is the thing that actually costs money. The line answers "is this going up?"
 * without hiding the day a bill jumped.
 */
export function movingAverage(values: number[], window: number): number[] {
  if (values.length === 0) return []
  const half = Math.floor(window / 2)
  return values.map((_, i) => {
    const from = Math.max(0, i - half)
    const to = Math.min(values.length, i + half + 1)
    const slice = values.slice(from, to)
    return slice.reduce((sum, v) => sum + v, 0) / slice.length
  })
}

/**
 * Vertical bars with the trend drawn over them.
 *
 * Bars are drawn as SVG rather than flexed divs so they can be a fixed, thin
 * share of each slot: a full-width block per day reads as a wall, and a wall
 * is hard to read a trend from. The last bar is highlighted because "today"
 * is the one a reader looks for first.
 */
export function BarChart({
  data,
  color = 'hsl(var(--primary))',
  accentColor = '#f97316',
  trendColor = 'hsl(var(--foreground))',
  height = 96,
  showTrend = true,
  formatValue,
}: {
  data: { value: number; label?: string }[]
  color?: string
  accentColor?: string
  trendColor?: string
  height?: number
  showTrend?: boolean
  formatValue?: (value: number) => string
}) {
  if (!data || data.length === 0) return null

  const W = 300
  const H = height
  const PAD_TOP = 4
  const max = Math.max(...data.map(d => d.value)) || 1
  const slot = W / data.length
  // Thin: a little over a third of each slot, with a floor so a 90-day range
  // still draws something, and a ceiling so three bars are not three planks.
  const barWidth = Math.max(1.5, Math.min(slot * 0.38, 14))
  const y = (value: number) => H - Math.max((value / max) * (H - PAD_TOP), 1)
  const label = (d: { value: number; label?: string }) =>
    `${d.label ? `${d.label}: ` : ''}${formatValue ? formatValue(d.value) : d.value.toFixed(2)}`

  const trend = showTrend && data.length >= 4
    ? movingAverage(data.map(d => d.value), trendWindow(data.length))
        .map((v, i) => `${(i * slot + slot / 2).toFixed(1)},${y(v).toFixed(1)}`)
        .join(' ')
    : ''

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      width="100%"
      height={height}
      style={{ display: 'block', overflow: 'visible' }}
      role="img"
    >
      {data.map((d, i) => {
        const last = i === data.length - 1
        const top = y(d.value)
        return (
          <rect
            key={i}
            x={i * slot + (slot - barWidth) / 2}
            y={top}
            width={barWidth}
            height={H - top}
            rx={Math.min(2, barWidth / 2)}
            fill={last ? accentColor : color}
            fillOpacity={last ? 1 : 0.55}
          >
            <title>{label(d)}</title>
          </rect>
        )
      })}
      {trend && (
        <polyline
          points={trend}
          fill="none"
          stroke={trendColor}
          strokeOpacity={0.5}
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  )
}
