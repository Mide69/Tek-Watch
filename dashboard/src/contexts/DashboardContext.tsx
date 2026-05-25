'use client'

import {
  createContext, useContext, useState, useEffect,
  useCallback, useRef, ReactNode,
} from 'react'

export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d'
export type Region   = 'all' | 'eu-west-2' | 'eu-west-1' | 'us-east-1'

export const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  '1h':  'Last 1 hour',
  '6h':  'Last 6 hours',
  '24h': 'Last 24 hours',
  '7d':  'Last 7 days',
  '30d': 'Last 30 days',
}

export const TIME_RANGE_OPTIONS: TimeRange[] = ['1h', '6h', '24h', '7d', '30d']

// How many data points and their interval for each time range
export const TIME_RANGE_CONFIG: Record<TimeRange, { points: number; intervalMs: number; label: string }> = {
  '1h':  { points: 12,  intervalMs: 5   * 60_000, label: '5 min' },
  '6h':  { points: 12,  intervalMs: 30  * 60_000, label: '30 min' },
  '24h': { points: 24,  intervalMs: 60  * 60_000, label: '1 hr' },
  '7d':  { points: 28,  intervalMs: 6   * 3_600_000, label: '6 hr' },
  '30d': { points: 30,  intervalMs: 24  * 3_600_000, label: '1 day' },
}

interface Toast {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
}

interface DashboardContextType {
  timeRange: TimeRange
  setTimeRange: (r: TimeRange) => void
  region: Region
  setRegion: (r: Region) => void
  lastUpdated: Date
  refreshKey: number
  refresh: () => void
  secondsToRefresh: number
  isRefreshing: boolean
  toasts: Toast[]
  addToast: (t: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

const REFRESH_INTERVAL = 30

const DashboardContext = createContext<DashboardContextType | null>(null)

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [timeRange, setTimeRangeState] = useState<TimeRange>('24h')
  const [region, setRegionState]       = useState<Region>('all')
  const [lastUpdated, setLastUpdated]  = useState(() => new Date())
  const [refreshKey, setRefreshKey]    = useState(0)
  const [secondsToRefresh, setSeconds] = useState(REFRESH_INTERVAL)
  const [isRefreshing, setIsRefreshing]= useState(false)
  const [toasts, setToasts]            = useState<Toast[]>([])
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(() => {
    setIsRefreshing(true)
    setLastUpdated(new Date())
    setRefreshKey(k => k + 1)
    setSeconds(REFRESH_INTERVAL)
    setTimeout(() => setIsRefreshing(false), 800)
  }, [])

  const addToast = useCallback((t: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2)
    setToasts(ts => [...ts, { ...t, id }])
    setTimeout(() => setToasts(ts => ts.filter(x => x.id !== id)), 5000)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(ts => ts.filter(t => t.id !== id))
  }, [])

  const setTimeRange = useCallback((r: TimeRange) => {
    setTimeRangeState(r)
    setRefreshKey(k => k + 1)
    setSeconds(REFRESH_INTERVAL)
  }, [])

  const setRegion = useCallback((r: Region) => {
    setRegionState(r)
    setRefreshKey(k => k + 1)
  }, [])

  // Auto-refresh countdown
  useEffect(() => {
    countdownRef.current = setInterval(() => {
      setSeconds(s => {
        if (s <= 1) { refresh(); return REFRESH_INTERVAL }
        return s - 1
      })
    }, 1000)
    return () => { if (countdownRef.current) clearInterval(countdownRef.current) }
  }, [refresh])

  return (
    <DashboardContext.Provider value={{
      timeRange, setTimeRange,
      region, setRegion,
      lastUpdated, refreshKey, refresh, secondsToRefresh, isRefreshing,
      toasts, addToast, removeToast,
    }}>
      {children}
    </DashboardContext.Provider>
  )
}

export function useDashboard() {
  const ctx = useContext(DashboardContext)
  if (!ctx) throw new Error('useDashboard must be used within DashboardProvider')
  return ctx
}
