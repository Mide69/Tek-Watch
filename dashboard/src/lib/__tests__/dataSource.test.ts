/**
 * Regression tests for the two defects that let a signed-in customer see a
 * fully populated dashboard of data that was not theirs:
 *   1. apiFetch sent no Authorization header, so every call 401'd.
 *   2. The mock fallback was silent, so the 401s looked like real data.
 */
// Controls whether this is a fixture view (demo) or a real signed-in account.
// demoMode reads the Cognito pool id once at import, so it cannot be steered
// by setting an env var mid-test.
let fixtureView = true
jest.mock('../demoMode', () => ({
  isFixtureView: () => fixtureView,
  isDemoSession: () => false,
}))

import { apiFetch, normaliseAgent } from '@/hooks/useData'
import { markDataSource, isShowingSampleData, resetDataSource } from '@/lib/dataSource'
import apiClient from '@/lib/api'

const FALLBACK = { total_resources: 847 }
const REAL = { total_resources: 3 }

describe('apiFetch', () => {
  beforeEach(() => resetDataSource())

  afterEach(() => {
    jest.restoreAllMocks()
    apiClient.clearToken()
  })

  it('sends the customer bearer token', async () => {
    apiClient.setToken('id-token-abc')
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => REAL,
    })
    global.fetch = fetchMock as unknown as typeof fetch

    await apiFetch('/api/v1/overview', FALLBACK)

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer id-token-abc')
  })

  it('returns real data untouched when the API answers', async () => {
    apiClient.setToken('id-token-abc')
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => REAL,
    }) as unknown as typeof fetch

    await expect(apiFetch('/api/v1/overview', FALLBACK)).resolves.toEqual(REAL)
  })

  it('does not call the API at all without a token', async () => {
    const fetchMock = jest.fn()
    global.fetch = fetchMock as unknown as typeof fetch

    await expect(apiFetch('/api/v1/overview', FALLBACK)).resolves.toEqual(FALLBACK)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('flags the fallback as sample data instead of passing it off as real', async () => {
    apiClient.setToken('expired')
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401 }) as unknown as typeof fetch

    const result = await apiFetch('/api/v1/cost/summary', FALLBACK)

    expect(result).toEqual(FALLBACK)
    expect(isShowingSampleData()).toBe(true)
  })

  it('clears the sample flag when the API recovers', async () => {
    apiClient.setToken('good')
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => REAL,
    }) as unknown as typeof fetch

    await apiFetch('/api/v1/cost/summary', FALLBACK)

    expect(isShowingSampleData()).toBe(false)
  })
})

describe('markDataSource', () => {
  beforeEach(() => resetDataSource())

  it('stays flagged while any single endpoint is still on sample data', () => {
    // One recovered endpoint must not clear a banner the others still warrant.
    markDataSource('/a', true)
    markDataSource('/b', true)
    markDataSource('/a', false)
    expect(isShowingSampleData()).toBe(true)

    markDataSource('/b', false)
    expect(isShowingSampleData()).toBe(false)
  })
})

describe('response envelopes', () => {
  beforeEach(() => {
    resetDataSource()
    apiClient.setToken('good')
  })
  afterEach(() => {
    jest.restoreAllMocks()
    apiClient.clearToken()
  })

  const respond = (body: unknown) => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => body,
    }) as unknown as typeof fetch
  }

  it('lifts the array out of the envelope the API actually sends', async () => {
    // /compute/ec2 answers {"instances": [...]}, the pages expect a bare array.
    // Without this the page ran (ec2 || []).filter on an object and threw
    // "filter is not a function" over the whole dashboard.
    respond({ instances: [{ id: 'i-1' }] })

    const result = await apiFetch('/api/v1/compute/ec2', [] as unknown[], 'instances')

    expect(result).toEqual([{ id: 'i-1' }])
    expect(isShowingSampleData()).toBe(false)
  })

  it('falls back to sample data when the shape is not what the page expects', async () => {
    // A wrong shape must degrade to the labelled sample view, never reach a
    // component that will call .filter on it.
    respond({ unexpected: 'shape' })

    const result = await apiFetch('/api/v1/compute/ec2', ['sample'], 'instances')

    expect(result).toEqual(['sample'])
    expect(isShowingSampleData()).toBe(true)
  })

  it('passes through a bare array unchanged', async () => {
    respond([{ id: 'i-1' }])
    await expect(apiFetch('/api/v1/compute/ec2', [] as unknown[], 'instances'))
      .resolves.toEqual([{ id: 'i-1' }])
  })
})

describe('normaliseAgent', () => {
  const FALLBACK = { collectors: [], regions: [] } as never

  it('maps the API field names onto what the page renders', () => {
    const result = normaliseAgent({
      status: 'healthy',
      regions_monitored: ['eu-west-2'],
      collectors_enabled: ['ec2', 'cost_explorer'],
      last_collection_time: '2026-09-01T00:00:00Z',
    }, FALLBACK) as never as { regions: string[]; collectors: { name: string; status: string }[] }

    expect(result.regions).toEqual(['eu-west-2'])
    expect(result.collectors.map(c => c.name)).toEqual(['EC2', 'COST EXPLORER'])
    expect(result.collectors.every(c => c.status === 'ok')).toBe(true)
  })

  it('does not invent counts the API never reported', () => {
    const result = normaliseAgent({
      status: 'healthy',
      collectors_enabled: ['ec2'],
    }, FALLBACK) as never as { collectors: { resources: null; metrics_sent: null }[] }

    expect(result.collectors[0].resources).toBeNull()
    expect(result.collectors[0].metrics_sent).toBeNull()
  })

  it('leaves an already-correct shape alone', () => {
    const shaped = { collectors: [{ name: 'EC2' }], regions: ['eu-west-2'] }
    expect(normaliseAgent(shaped, FALLBACK)).toBe(shaped)
  })

  it('returns null for a non-object so the caller can fall back', () => {
    expect(normaliseAgent('nonsense', FALLBACK)).toBeNull()
    expect(normaliseAgent(null, FALLBACK)).toBeNull()
  })
})

describe('what a real account sees before connecting anything', () => {
  beforeEach(() => {
    resetDataSource()
    apiClient.setToken('good')
    fixtureView = false
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401 }) as unknown as typeof fetch
  })
  afterEach(() => {
    jest.restoreAllMocks()
    apiClient.clearToken()
    fixtureView = true
  })

  it('gets zeros, not somebody elses figures', async () => {
    // The point of the change: a brand new account must not open on 847
    // resources and 4,247.80 of monthly spend belonging to nobody.
    const result = await apiFetch('/api/v1/overview', {
      total_resources: 847,
      estimated_monthly_cost: 4247.8,
      active_alarms: 3,
      agent_status: { status: 'healthy', last_seen: 'x' },
      cost_trend: [{ cost: 1, label: 'a' }],
    })

    expect(result).toEqual({
      total_resources: 0,
      estimated_monthly_cost: 0,
      active_alarms: 0,
      agent_status: { status: '', last_seen: '' },
      cost_trend: [],
    })
  })

  it('empties lists rather than inventing rows', async () => {
    await expect(apiFetch('/api/v1/compute/ec2', [{ id: 'i-fake' }], 'instances'))
      .resolves.toEqual([])
  })

  it('still raises the banner, so the zeros are explained', async () => {
    await apiFetch('/api/v1/overview', { total_resources: 847 })
    expect(isShowingSampleData()).toBe(true)
  })

  it('keeps the fixtures for a demo view', async () => {
    // The demo exists to show what a populated dashboard looks like.
    fixtureView = true
    await expect(apiFetch('/api/v1/overview', { total_resources: 847 }))
      .resolves.toEqual({ total_resources: 847 })
  })
})

describe('keys the API does not send', () => {
  beforeEach(() => {
    resetDataSource()
    apiClient.setToken('good')
  })
  afterEach(() => {
    jest.restoreAllMocks()
    apiClient.clearToken()
  })

  const respond = (body: unknown) => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => body,
    }) as unknown as typeof fetch
  }

  it('fills a missing key with empty, not with the fixture value', async () => {
    // The live crash: /overview returns no cost_trend, the page read
    // data.cost_trend[0], and "Cannot read properties of undefined" replaced
    // the dashboard. Filling from the fixture would have shown a stranger's
    // cost history instead, which is worse.
    respond({ total_resources: 4 })

    const result = await apiFetch('/api/v1/overview', {
      total_resources: 847,
      cost_trend: [{ cost: 1, label: 'a' }],
    })

    expect(result).toEqual({ total_resources: 4, cost_trend: [] })
  })

  it('lets real values win over the defaults', async () => {
    respond({ total_resources: 4, cost_trend: [{ cost: 9, label: 'b' }] })

    const result = await apiFetch('/api/v1/overview', {
      total_resources: 847,
      cost_trend: [{ cost: 1, label: 'a' }],
    })

    expect(result).toEqual({ total_resources: 4, cost_trend: [{ cost: 9, label: 'b' }] })
  })

  it('keeps an explicit null from the API rather than overriding it', async () => {
    respond({ total_resources: 4, agent_status: null })

    const result = await apiFetch('/api/v1/overview', {
      total_resources: 847,
      agent_status: { status: 'healthy' },
    })

    expect(result).toEqual({ total_resources: 4, agent_status: null })
  })

  it('does not touch array payloads', async () => {
    respond({ instances: [{ id: 'i-1' }] })
    await expect(apiFetch('/api/v1/compute/ec2', [{ id: 'mock' }], 'instances'))
      .resolves.toEqual([{ id: 'i-1' }])
  })
})
