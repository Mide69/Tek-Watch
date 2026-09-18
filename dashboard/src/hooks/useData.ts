'use client'

/**
 * Unified SWR data hooks for all dashboard pages.
 * Each hook:
 *  1. Tries the real API, authenticated, with a 4-second timeout
 *  2. Falls back to time-range-aware mock data on any failure, and records
 *     that it did so (see lib/dataSource) so the UI can say as much
 *  3. Keyed on [endpoint, timeRange, region, refreshKey] so the chart
 *     re-renders when any filter changes
 */

import useSWR from 'swr'
import { useDashboard } from '@/contexts/DashboardContext'
import apiClient from '@/lib/api'
import { markDataSource } from '@/lib/dataSource'
import { isFixtureView } from '@/lib/demoMode'
import {
  getMockOverview, getMockEC2WithMetrics, getMockLambdaWithMetrics,
  getMockRDSWithMetrics, getMockCostSummary, MOCK_COST_BREAKDOWN,
  MOCK_ALERTS, MOCK_AGENT, MOCK_ECS, MOCK_DYNAMODB, MOCK_VPCS,
  MOCK_ELBS, MOCK_CLOUDFRONT, MOCK_S3, MOCK_SQS, MOCK_SNS,
  MOCK_GUARDDUTY, MOCK_IAM, MOCK_ACM_CERTS, MOCK_CW_ALARMS,
  MOCK_COMPLIANCE, MOCK_INCIDENTS, MOCK_EVIDENCE, MOCK_CALENDAR, type EvidenceLog,
} from '@/lib/mockData'

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

/**
 * The same shape, emptied out: arrays cleared, numbers zeroed, strings blanked.
 *
 * What a real customer sees before they have connected anything. Serving them
 * the mock fixtures instead meant a brand new account opened on 847 resources,
 * three active alarms and £4,247 of monthly spend belonging to nobody. A
 * labelled banner above invented figures is still invented figures; zero is
 * the true answer to "what is in your AWS account" when the answer is nothing.
 *
 * The demo keeps the fixtures. Showing what a populated dashboard looks like
 * is the entire job of the demo, and it is labelled as such.
 */
function emptyLike<T>(value: T): T {
  if (Array.isArray(value)) return [] as unknown as T
  if (value === null || value === undefined) return value
  if (typeof value === 'number') return 0 as unknown as T
  if (typeof value === 'string') return '' as unknown as T
  if (typeof value === 'boolean') return false as unknown as T
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = emptyLike(v)
    }
    return out as unknown as T
  }
  return value
}

/**
 * Lift the payload out of the envelope the API actually returns.
 *
 * Every list endpoint wraps its array in a single-key object — /compute/ec2
 * answers {"instances": [...]}, /storage/s3 answers {"buckets": [...]} — while
 * every mock fallback here is a bare array. The pages were written against the
 * mock shape and, because the dashboard never sent an auth header, no page had
 * ever rendered a real response: the 401 fell back to mock on every request.
 *
 * The moment authentication started working, real data arrived and
 * `(ec2 || []).filter(...)` threw "filter is not a function" on a customer's
 * screen — the `|| []` only ever guarded null, not an object.
 */
function unwrap<T>(payload: unknown, fallback: T, pick?: string): T | null {
  const lifted =
    pick && payload && typeof payload === 'object' && !Array.isArray(payload) && pick in payload
      ? (payload as Record<string, unknown>)[pick]
      : payload

  // Shape guard. If the API ever answers with something other than what the
  // page expects, show sample data and say so, rather than handing a component
  // an object it will call .filter on and blanking the whole dashboard.
  if (lifted === null || lifted === undefined) return null

  // Both directions. A page written against an array that receives an object
  // calls .filter on it; a page written against an object that receives an
  // array reads .breakdown off it and gets undefined. Either way the mismatch
  // must stop here and fall back to a labelled empty view, not reach a
  // component. Both have now happened in production.
  const fallbackIsArray = Array.isArray(fallback)
  const liftedIsArray = Array.isArray(lifted)
  if (fallbackIsArray !== liftedIsArray) return null
  if (!fallbackIsArray && typeof fallback === 'object' && typeof lifted !== 'object') return null

  // Guarantee every key the page reads exists, defaulted to empty.
  //
  // The API's overview returns no cost_trend; only the fixtures have one. The
  // page read data.cost_trend[0] and threw "Cannot read properties of
  // undefined" the moment real data arrived — the third crash of this exact
  // shape, after .filter on an envelope and .map on the same missing field.
  // Guarding each site as it surfaces is a losing game: any key the API stops
  // sending is another blank screen.
  //
  // Defaults come from emptyLike, never from the fixtures, so a field the API
  // does not send reads as empty rather than as somebody else's number. Real
  // values always win.
  if (
    lifted && typeof lifted === 'object' && !Array.isArray(lifted) &&
    fallback && typeof fallback === 'object' && !Array.isArray(fallback)
  ) {
    return { ...emptyLike(fallback), ...lifted } as T
  }

  return lifted as T
}

/**
 * What a page paints before its first response arrives.
 *
 * SWR renders fallbackData immediately, and that was always the fixtures — so
 * a signed-in customer saw 847 resources and a stranger's IAM figures on every
 * page transition, for as long as the request took. That is the flash of demo
 * data on every click. apiFetch already returns zeros to a real account; this
 * makes the first paint agree with the answer that follows it.
 *
 * Safe to call during render: it reads local storage, which is absent
 * server-side, so prerendering yields the empty shape. The dashboard layout
 * does not paint page content until the viewer is known, so the server never
 * commits to the other branch and there is nothing to mismatch on hydration.
 */
function initial<T>(mock: T): T {
  return isFixtureView() ? mock : emptyLike(mock)
}

// Exported for tests: the defects this guards against (missing auth header,
// silent mock fallback, envelope mismatch) were all invisible from the outside.
export async function apiFetch<T>(path: string, fallback: T, pick?: string): Promise<T> {
  // A visitor who opted into the demo, or a build with no Cognito at all,
  // gets the fixtures. A signed-in customer gets zeros.
  const sample = (): T => {
    markDataSource(path, true)
    return isFixtureView() ? fallback : emptyLike(fallback)
  }

  // Every one of these endpoints is behind get_current_customer on the API.
  // This used to be a bare fetch() with no Authorization header, so every
  // request came back 401 and the catch below quietly served mock data — a
  // signed-in customer saw a dashboard of resources and costs that were not
  // theirs, presented exactly as if they were.
  const token = apiClient.getToken()
  if (!token) return sample()

  try {
    const controller = new AbortController()
    const tid = setTimeout(() => controller.abort(), 4000)
    const res = await fetch(`${API}${path}`, {
      signal: controller.signal,
      headers: { Authorization: `Bearer ${token}` },
    })
    clearTimeout(tid)
    if (!res.ok) return sample()

    const data = unwrap(await res.json(), fallback, pick)
    if (data === null) return sample()

    markDataSource(path, false)
    return data
  } catch {
    return sample()
  }
}

// ─── Overview ────────────────────────────────────────────────────────────────

export function useOverview() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `overview|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockOverview(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/overview?range=${timeRange}&region=${region}`, fallback), {
    revalidateOnFocus: false,
    fallbackData: initial(fallback),
  })
}

// ─── Compute ─────────────────────────────────────────────────────────────────

export function useEC2() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `ec2|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockEC2WithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/compute/ec2?range=${timeRange}&region=${region}`, fallback, 'instances'), {
    revalidateOnFocus: false,
    fallbackData: initial(fallback),
  })
}

export function useLambda() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `lambda|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockLambdaWithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/compute/lambda?range=${timeRange}&region=${region}`, fallback, 'functions'), {
    revalidateOnFocus: false,
    fallbackData: initial(fallback),
  })
}

export function useECS() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `ecs|${timeRange}|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/compute/ecs?region=${region}`, MOCK_ECS, 'services'), {
    revalidateOnFocus: false,
    fallbackData: initial(MOCK_ECS),
  })
}

// ─── Databases ───────────────────────────────────────────────────────────────

export function useRDS() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `rds|${timeRange}|${region}|${refreshKey}`
  const fallback = getMockRDSWithMetrics(timeRange)
  return useSWR(key, () => apiFetch(`/api/v1/databases/rds?range=${timeRange}&region=${region}`, fallback, 'instances'), {
    revalidateOnFocus: false,
    fallbackData: initial(fallback),
  })
}

export function useDynamoDB() {
  const { region, refreshKey } = useDashboard()
  const key = `dynamodb|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/databases/dynamodb?region=${region}`, MOCK_DYNAMODB, 'tables'), {
    revalidateOnFocus: false,
    fallbackData: initial(MOCK_DYNAMODB),
  })
}

// ─── Networking ──────────────────────────────────────────────────────────────

export function useNetworking() {
  const { region, refreshKey } = useDashboard()
  const key = `networking|${region}|${refreshKey}`
  return useSWR(key, async () => {
    const [vpcs, elbs, cf] = await Promise.all([
      apiFetch(`/api/v1/networking/vpc?region=${region}`, MOCK_VPCS, 'resources'),
      apiFetch(`/api/v1/networking/elb?region=${region}`, MOCK_ELBS, 'load_balancers'),
      apiFetch('/api/v1/networking/cloudfront', MOCK_CLOUDFRONT, 'distributions'),
    ])
    return { vpcs, elbs, cloudfront: cf }
  }, {
    revalidateOnFocus: false,
    fallbackData: initial({ vpcs: MOCK_VPCS, elbs: MOCK_ELBS, cloudfront: MOCK_CLOUDFRONT }),
  })
}

// ─── Storage ─────────────────────────────────────────────────────────────────

export function useStorage() {
  const { region, refreshKey } = useDashboard()
  const key = `storage|${region}|${refreshKey}`
  return useSWR(key, () => apiFetch(`/api/v1/storage/s3?region=${region}`, MOCK_S3, 'buckets'), {
    revalidateOnFocus: false,
    fallbackData: initial(MOCK_S3),
  })
}

// ─── Messaging ───────────────────────────────────────────────────────────────

export function useMessaging() {
  const { region, refreshKey } = useDashboard()
  const key = `messaging|${region}|${refreshKey}`
  return useSWR(key, async () => {
    const [sqs, sns] = await Promise.all([
      apiFetch(`/api/v1/messaging/sqs?region=${region}`, MOCK_SQS, 'queues'),
      apiFetch(`/api/v1/messaging/sns?region=${region}`, MOCK_SNS, 'topics'),
    ])
    return { sqs, sns }
  }, {
    revalidateOnFocus: false,
    fallbackData: initial({ sqs: MOCK_SQS, sns: MOCK_SNS }),
  })
}

// ─── Security ────────────────────────────────────────────────────────────────

export function useSecurity() {
  const { timeRange, region, refreshKey } = useDashboard()
  const key = `security|${timeRange}|${region}|${refreshKey}`
  // Compliance used to be getMockComplianceScore(): four fixed percentages
  // shown to every signed-in customer as if they were theirs. It now comes
  // from the API's rule engine, and only the demo sees fixtures.
  return useSWR(key, async () => {
    const [guardduty, iam, certs, alarms, compliance, incidents, evidence, verification, calendar] = await Promise.all([
      apiFetch(`/api/v1/security/guardduty?region=${region}`, MOCK_GUARDDUTY, 'findings'),
      apiFetch('/api/v1/security/iam', MOCK_IAM, 'summary'),
      apiFetch('/api/v1/security/acm', MOCK_ACM_CERTS, 'certificates'),
      apiFetch(`/api/v1/security/alarms?region=${region}`, MOCK_CW_ALARMS, 'alarms'),
      apiFetch('/api/v1/security/compliance', MOCK_COMPLIANCE),
      apiFetch('/api/v1/security/incidents', MOCK_INCIDENTS, 'incidents'),
      apiFetch('/api/v1/security/evidence', MOCK_EVIDENCE),
      apiFetch('/api/v1/security/evidence/verify', MOCK_EVIDENCE.verification),
      apiFetch('/api/v1/security/calendar', MOCK_CALENDAR),
    ])
    return { guardduty, iam, certs, alarms, compliance, incidents, calendar,
             evidence: { ...evidence, verification } as EvidenceLog }
  }, {
    revalidateOnFocus: false,
    fallbackData: initial({
      guardduty: MOCK_GUARDDUTY,
      iam: MOCK_IAM,
      certs: MOCK_ACM_CERTS,
      alarms: MOCK_CW_ALARMS,
      compliance: MOCK_COMPLIANCE,
      incidents: MOCK_INCIDENTS,
      evidence: MOCK_EVIDENCE,
      calendar: MOCK_CALENDAR,
    }),
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
      // No unwrap here: MOCK_COST_BREAKDOWN is already { breakdown: [...] },
      // the same shape the API sends, and the page reads breakdown.breakdown.
      // Lifting the array out left the page calling .map on undefined.
      apiFetch('/api/v1/cost/breakdown', MOCK_COST_BREAKDOWN),
    ])
    return { summary, breakdown }
  }, {
    revalidateOnFocus: false,
    fallbackData: initial({ summary: fallbackSummary, breakdown: MOCK_COST_BREAKDOWN }),
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
      fallbackData: initial(fallback),
      refreshInterval: 30_000,
    },
  )
}

// ─── Agent ───────────────────────────────────────────────────────────────────

/**
 * Reshape /agent/health into what the agent page renders.
 *
 * The API answers with regions_monitored and collectors_enabled — a plain list
 * of collector names — while the page was written against the mock, which has
 * `regions`, and `collectors` as objects with per-collector run detail. Reading
 * a.collectors.filter on the real response threw before the page could paint.
 *
 * Fields the API genuinely does not report (per-collector resource counts,
 * metrics sent, agent version, uptime) are left null rather than invented, and
 * the page prints an em dash for them. Showing a plausible number for something
 * nobody measured is how the fabricated dashboard happened in the first place.
 */
export function normaliseAgent(raw: unknown, fallback: typeof MOCK_AGENT) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const r = raw as Record<string, any>

  // Already in the page's shape (the mock, or a future API that matches).
  if (Array.isArray(r.collectors) && Array.isArray(r.regions)) return r as typeof fallback

  const names: unknown[] = Array.isArray(r.collectors_enabled) ? r.collectors_enabled : []
  const agentOk = r.status === 'healthy'

  return {
    ...fallback,
    customer_id: r.customer_id ?? fallback.customer_id,
    status: r.status ?? 'unknown',
    last_heartbeat: r.last_heartbeat ?? null,
    regions: Array.isArray(r.regions_monitored) ? r.regions_monitored : [],
    // The API reports which collectors are enabled, not how each one fared, so
    // status tracks the agent as a whole rather than claiming per-collector health.
    collectors: names.map(name => ({
      name: String(name).toUpperCase().replace(/_/g, ' '),
      status: agentOk ? 'ok' : String(r.status ?? 'unknown'),
      last_run: r.last_collection_time ?? null,
      resources: null,
      metrics_sent: null,
    })),
    version: null,
    uptime_hours: null,
    metrics_collected_total: null,
    collection_interval_s: null,
  } as unknown as typeof fallback
}

export function useAgent() {
  const { refreshKey } = useDashboard()
  const key = `agent|${refreshKey}`
  return useSWR(key, async () => {
    const raw = await apiFetch<unknown>('/api/v1/agent/health', MOCK_AGENT)
    return normaliseAgent(raw, MOCK_AGENT) ?? MOCK_AGENT
  }, {
    revalidateOnFocus: false,
    fallbackData: initial(MOCK_AGENT),
  })
}
