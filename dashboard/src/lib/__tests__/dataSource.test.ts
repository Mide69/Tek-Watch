/**
 * Regression tests for the two defects that let a signed-in customer see a
 * fully populated dashboard of data that was not theirs:
 *   1. apiFetch sent no Authorization header, so every call 401'd.
 *   2. The mock fallback was silent, so the 401s looked like real data.
 */
import { apiFetch } from '@/hooks/useData'
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
