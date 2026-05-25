/** Tiny SVG sparkline — no Recharts, no ResizeObserver, no renderer issues */

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

/** Vertical bar chart for cost/time series */
export function BarChart({
  data,
  color = '#6366f1',
  accentColor = '#f97316',
  height = 96,
}: {
  data: { value: number; label?: string }[]
  color?: string
  accentColor?: string
  height?: number
}) {
  if (!data || data.length === 0) return null
  const max = Math.max(...data.map(d => d.value)) || 1
  return (
    <div style={{ height }} className="flex items-end gap-0.5">
      {data.map((d, i) => {
        const pct  = (d.value / max) * 100
        const last = i === data.length - 1
        return (
          <div
            key={i}
            className="flex-1 rounded-sm min-h-[2px]"
            style={{
              height:     `${Math.max(pct, 2)}%`,
              background: last ? accentColor : color,
              opacity:    last ? 1 : 0.55,
            }}
            title={d.label ? `${d.label}: ${d.value.toFixed(2)}` : d.value.toFixed(2)}
          />
        )
      })}
    </div>
  )
}
