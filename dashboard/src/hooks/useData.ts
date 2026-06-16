'use client'

/**
 * Unified SWR data hooks for all dashboard pages.
 * Each hook:
 *  1. Tries the real API (with 4-second timeout)
 *  2. Falls back to time-range-aware mock data on any failure
 *  3. Keyed on [endpoint, timeRange, region, refreshKey] so the chart
 *     re-renders when any filter changes
 */

import useSWR from 'swr'
import { useDashboard } from '@/contexts/DashboardContext'
import {
  getMockOverview, getMockEC2WithMetrics, getMockLambdaWithMetrics,
  getMockRDSWithMetrics, getMockCostSummary, MOCK_COST_BREAKDOWN,
  MOCK_ALERTS, MOCK_AGENT, MOCK_ECS, MOCK_DYNAMODB, MOCK_VPCS,
  MOCK_ELBS, MOCK_CLOUDFRONT, MOCK_S3, MOCK_SQS, MOCK_SNS,
  MOCK_GUARDDUTY, MOCK_IAM, MOCK_ACM_CERTS, MOCK_CW_ALARMS,
  getMockComplianceScore,
} from '@/lib/mockData'

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 4000)
    const res = await fetch(`${API}${path}`, { signal: controller.signal })
    clearTimeout(tid)
    if (!res.ok) return fallback
    return res.json() as Promise<T>
  } catch {
    return fallback
  }
}

// ─── Overview ────────────────────────────────────────────────────────────────

export function useOverview() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `overview|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockOverview(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/overview?range=${timeRange}&region=${region}`, fallback), {
    revalidateOnFocus: false,
    fallbackData: fallback,
  })
}

// ─── Compute ─────────────────────────────────────────────────────────────────

export function useEC2() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `ec2|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockEC2WithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/compute/ec2?range=${timeRange}&region=${region}`, fallback), {
    revalidateOnFocus: false,
    fallbackData: fallback,
  })
}

export function useLambda() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `lambda|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockLambdaWithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/compute/lambda?range=${timeRange}&region=${region}`, fallback), {
    revalidateOnFocus: false,
    fallbackData: fallback,
  })
}

export function useECS() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `ecs|${timeRange}|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/compute/ecs?region=${region}`, MOCK_ECS), {
    revalidateOnFocus: false,
    fallbackData: MOCK_ECS,
  })
}

// ─── Databases ───────────────────────────────────────────────────────────────

export function useRDS() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `rds|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockRDSWithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/databases/rds?range=${timeRange}&region=${region}`, fallback), {
    revalidateOnFocus: false,
    fallbackData: fallback,
  })
}

export function useDynamoDB() {
  const { region, refreshKey } = useDashboard()
  const key = `dynamodb|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/databases/dynamodb?region=${region}`, MOCK_DYNAMODB), {
    revalidateOnFocus: false,
    fallbackData: MOCK_DYNAMODB,
  })
}

// ─── Networking ──────────────────────────────────────────────────────────────

export function useNetworking() {
  const { region, refreshKey } = useDashboard()
  const key = `networking|${region}|${refreshKey}`
  return useSWR(key, async () => {
    const [vpcs, elbs, cf] = await Promise.all([
      apiFetch(`/api/v1/networking/vpc?region=${region}`, MOCK_VPCS),
      apiFetch(`/api/v1/networking/elb?region=${region}`, MOCK_ELBS),
      apiFetch('/api/v1/networking/cloudfront', MOCK_CLOUDFRONT),
    ])
    return { vpcs, elbs, cloudfront: cf }
  }, {
    revalidateOnFocus: false,
    fallbackData: { vpcs: MOCK_VPCS, elbs: MOCK_ELBS, cloudfront: MOCK_CLOUDFRONT },
  })
}

// ─── Storage ─────────────────────────────────────────────────────────────────

export function useStorage() {
  const { region, refreshKey } = useDashboard()
  const key = `storage|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/storage/s3?region=${region}`, MOCK_S3), {
    revalidateOnFocus: false,
    fallbackData: MOCK_S3,
  })
}

// ─── Messaging ───────────────────────────────────────────────────────────────

export function useMessaging() {
  const { region, refreshKey } = useDashboard()
  const key = `messaging|${region}|${refreshKey}`
  return useSWR(key, async () => {
    const [sqs, sns] = await Promise.all([
      apiFetch(`/api/v1/messaging/sqs?region=${region}`, MOCK_SQS),
      apiFetch(`/api/v1/messaging/sns?region=${region}`, MOCK_SNS),
    ])
    return { sqs, sns }
  }, {
    revalidateOnFocus: false,
    fallbackData: { sqs: MOCK_SQS, sns: MOCK_SNS },
  })
}

// ─── Security ────────────────────────────────────────────────────────────────

export function useSecurity() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `security|${timeRange}|${region}|${refreshKey}`
  const fallbackCompliance = getMockComplianceScore(timeRange)
  return useSWR(key, async () => {
    const [guardduty, iam, certs, alarms] = await Promise.all([
      apiFetch(`/api/v1/security/guardduty?region=${region}`, MOCK_GUARDDUTY),
      apiFetch('/api/v1/security/iam', MOCK_IAM),
      apiFetch('/api/v1/security/acm', MOCK_ACM_CERTS),
      apiFetch(`/api/v1/security/alarms?region=${region}`, MOCK_CW_ALARMS),
    ])
    return { guardduty, iam, certs, alarms, compliance: fallbackCompliance }
  }, {
    revalidateOnFocus: false,
    fallbackData: {
      guardduty: MOCK_GUARDDUTY,
      iam: MOCK_IAM,
      certs: MOCK_ACM_CERTS,
      alarms: MOCK_CW_ALARMS,
      compliance: fallbackCompliance,
    },
  })
}

// ─── Cost ────────────────────────────────────────────────────────────────────

export function useCost() {
  const { timeRange, refreshKey } = useDashboard()
  const key = `cost|${timeRange}|${refreshKey}`
  const fallbackSummary = getMockCostSummary(timeRange)
  return useSWR(key, async () => {
    const [summary, breakdown] = await Promise.all([
      apiFetch(`/api/v1/cost/summary?range=${timeRange}`, fallbackSummary),
      apiFetch('/api/v1/cost/breakdown', MOCK_COST_BREAKDOWN),
    ])
    return { summary, breakdown }
  }, {
    revalidateOnFocus: false,
    fallbackData: { summary: fallbackSummary, breakdown: MOCK_COST_BREAKDOWN },
  })
}

// ─── Alerts ──────────────────────────────────────────────────────────────────

export type AlertStatus = 'active' | 'acknowledged'

export interface Alert {
  alert_id: string
  severity: string
  status: AlertStatus
  type: string
  service: string
  resource: string
  description: string
  triggered_at: string
  current_value?: number
  threshold_value?: number | null
  recommendation?: string
  acknowledged_at?: string
}

export interface AlertsPage {
  alerts: Alert[]
  total: number
  limit: number
  offset: number
}

export function useAlerts(limit = 100, offset = 0) {
  const { refreshKey } = useDashboard()
  const key = `alerts|${refreshKey}|${limit}|${offset}`
  const fallback: AlertsPage = { alerts: MOCK_ALERTS, total: MOCK_ALERTS.length, limit, offset }
  return useSWR(
    key,
    async () => {
      const res = await apiFetch<AlertsPage | Alert[]>(
        `/api/v1/alerts?limit=${limit}&offset=${offset}`,
        fallback,
      )
      if (Array.isArray(res)) return { alerts: res, total: res.length, limit, offset }
      return res as AlertsPage
    },
    {
      revalidateOnFocus: false,
      fallbackData: fallback,
      refreshInterval: 30_000,
    },
  )
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export function useAgent() {
  const { refreshKey } = useDashboard()
  const key = `agent|${refreshKey}`
  return useSWR(key, () => apiFetch('/api/v1/agent/health', MOCK_AGENT), {
    revalidateOnFocus: false,
    fallbackData: MOCK_AGENT,
  })
}
