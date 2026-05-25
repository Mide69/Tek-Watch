/**
 * useAlerts — SWR hook for fetching alerts with auto-refresh.
 */
import useSWR from 'swr'
import apiClient from '@/lib/api'

interface UseAlertsOptions {
  statusFilter?: 'active' | 'acknowledged' | 'all'
  refreshInterval?: number
}

export function useAlerts({
  statusFilter = 'all',
  refreshInterval = 30_000,
}: UseAlertsOptions = {}) {
  const filter = statusFilter === 'all' ? undefined : statusFilter
  const key = `alerts/${statusFilter}`

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => apiClient.getAlerts(filter),
    {
      refreshInterval,
      revalidateOnFocus: true,
      dedupingInterval: 10_000,
    }
  )

  return {
    alerts: data?.alerts ?? [],
    loading: isLoading,
    error,
    refresh: mutate,
  }
}
