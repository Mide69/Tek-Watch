/**
 * useMetrics — SWR hook for fetching time-series metrics with auto-refresh.
 */
import useSWR from 'swr'
import apiClient from '@/lib/api'

type TimeRange = '24h' | '7d' | '30d' | '90d'

interface UseMetricsOptions {
  resourceId: string | null
  metricName: string
  timeRange?: TimeRange
  refreshInterval?: number
}

export function useMetrics({
  resourceId,
  metricName,
  timeRange = '24h',
  refreshInterval = 60_000,
}: UseMetricsOptions) {
  const key = resourceId
    ? `metrics/${resourceId}/${metricName}/${timeRange}`
    : null

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => apiClient.getResourceMetrics(resourceId!, metricName, timeRange),
    {
      refreshInterval,
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
    }
  )

  return {
    data: data?.data ?? [],
    loading: isLoading,
    error,
    refresh: mutate,
  }
}

export function useOverview(region?: string, refreshInterval = 60_000) {
  const key = `overview/${region ?? 'all'}`
  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => apiClient.getOverview(region),
    { refreshInterval, revalidateOnFocus: false }
  )
  return { data, loading: isLoading, error, refresh: mutate }
}

export function useEC2(region?: string, refreshInterval = 60_000) {
  const { data, error, isLoading, mutate } = useSWR(
    `ec2/${region ?? 'all'}`,
    () => apiClient.getEC2Instances(region),
    { refreshInterval, revalidateOnFocus: false }
  )
  return { data, loading: isLoading, error, refresh: mutate }
}

export function useLambda(region?: string, refreshInterval = 60_000) {
  const { data, error, isLoading, mutate } = useSWR(
    `lambda/${region ?? 'all'}`,
    () => apiClient.getLambdaFunctions(region),
    { refreshInterval, revalidateOnFocus: false }
  )
  return { data, loading: isLoading, error, refresh: mutate }
}
