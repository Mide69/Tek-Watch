/**
 * @jest-environment jsdom
 */
/**
 * AuthProvider resolves the signed-in customer once per browser session, not
 * once per page.
 *
 * It used to be a plain hook every page called at its own top level. Next.js
 * tears down and rebuilds each page's component on every route change, so
 * that meant a fresh instance — fresh state, fresh effect, a fresh Cognito
 * session lookup — on every single click through the sidebar. Someone
 * navigating faster than that lookup resolved cancelled it mid-flight before
 * its own correction (revalidating every stale SWR key, clearing the global
 * sample-data flag) ever ran, leaving whatever an earlier, abandoned attempt
 * had already fetched on screen — sample data, or empty zeros — with nothing
 * left mounted to ever ask again.
 *
 * These tests exercise the provider directly rather than through a rendered
 * page, since there is no @testing-library/react in this project; React's
 * own act() + createRoot is enough to mount it, flush its effect, and read
 * what it published.
 */
import { act } from 'react-dom/test-utils'
import { createRoot, type Root } from 'react-dom/client'

const revalidateAll = jest.fn()
jest.mock('swr', () => ({ mutate: (...args: unknown[]) => revalidateAll(...args) }))

const resetDataSource = jest.fn()
jest.mock('@/lib/dataSource', () => ({ resetDataSource: () => resetDataSource() }))

const isMisconfigured = jest.fn(() => false)
const isDemoBuild = jest.fn(() => false)
const isDemoSession = jest.fn(() => false)
jest.mock('@/lib/demoMode', () => ({
  isMisconfigured: () => isMisconfigured(),
  isDemoBuild: () => isDemoBuild(),
  isDemoSession: () => isDemoSession(),
}))

const getAuthUser = jest.fn()
const configureAmplify = jest.fn()
jest.mock('@/lib/auth', () => ({
  configureAmplify: () => configureAmplify(),
  getAuthUser: () => getAuthUser(),
}))

const setToken = jest.fn()
jest.mock('@/lib/api', () => ({ __esModule: true, default: { setToken: (t: string) => setToken(t) } }))

import { AuthProvider, useAuth } from '../useAuth'

function Probe() {
  const { customerId, loading } = useAuth()
  return <div data-testid="probe" data-customer={customerId ?? ''} data-loading={String(loading)} />
}

function flush() {
  // Two microtask turns: one for the dynamic import() calls inside check(),
  // one for the getAuthUser() promise they resolve to.
  return act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
  })
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  jest.clearAllMocks()
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  jest.restoreAllMocks()
})

function render() {
  act(() => {
    root.render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
  })
}

describe('a signed-in customer', () => {
  beforeEach(() => {
    getAuthUser.mockResolvedValue({ customerId: 'TT-9F4KQ7M2', email: 'a@b.com', idToken: 'id-token' })
  })

  it('publishes the customer id once the session resolves', async () => {
    render()
    await flush()
    const probe = container.querySelector('[data-testid="probe"]')!
    expect(probe.getAttribute('data-customer')).toBe('TT-9F4KQ7M2')
    expect(probe.getAttribute('data-loading')).toBe('false')
  })

  it('sets the api client token before anything else reads it', async () => {
    render()
    await flush()
    expect(setToken).toHaveBeenCalledWith('id-token')
  })

  it('clears the global sample-data flag and revalidates every cached fetch', async () => {
    // This is the fix: a hook whose first fetch raced ahead of the token
    // being set marks itself as sample data and nothing used to correct it.
    // The provider must clear that slate and force a fresh fetch the moment
    // the token becomes available.
    render()
    await flush()
    expect(resetDataSource).toHaveBeenCalledTimes(1)
    expect(revalidateAll).toHaveBeenCalledTimes(1)
    // Called with a predicate matching every key, not one specific path —
    // it does not know in advance which hook, if any, raced.
    const predicate = revalidateAll.mock.calls[0][0]
    expect(predicate('any/swr/key/at/all')).toBe(true)
  })

  it('resets the slate strictly after the token is set, not before', async () => {
    render()
    await flush()
    const tokenCallOrder = setToken.mock.invocationCallOrder[0]
    const resetCallOrder = resetDataSource.mock.invocationCallOrder[0]
    expect(tokenCallOrder).toBeLessThan(resetCallOrder)
  })
})

describe('no session', () => {
  it('redirects to /login rather than rendering a blank dashboard', async () => {
    getAuthUser.mockResolvedValue(null)
    const replace = jest.fn()
    Object.defineProperty(window, 'location', { value: { replace }, writable: true })

    render()
    await flush()

    expect(replace).toHaveBeenCalledWith('/login')
    expect(setToken).not.toHaveBeenCalled()
    expect(revalidateAll).not.toHaveBeenCalled()
  })
})

describe('a demo tab', () => {
  it('resolves to TT-DEMO without ever calling Cognito', async () => {
    isDemoSession.mockReturnValue(true)
    render()
    await flush()

    const probe = container.querySelector('[data-testid="probe"]')!
    expect(probe.getAttribute('data-customer')).toBe('TT-DEMO')
    expect(getAuthUser).not.toHaveBeenCalled()
    expect(revalidateAll).not.toHaveBeenCalled()
  })
})

describe('a misconfigured deployment', () => {
  it('stays unresolved rather than pretending to be a demo or a signed-in account', async () => {
    isMisconfigured.mockReturnValue(true)
    render()
    await flush()

    const probe = container.querySelector('[data-testid="probe"]')!
    expect(probe.getAttribute('data-customer')).toBe('')
    expect(getAuthUser).not.toHaveBeenCalled()
  })
})

describe('a consumer outside the provider', () => {
  it('gets the default, unresolved state rather than throwing', () => {
    act(() => {
      root.render(<Probe />)
    })
    const probe = container.querySelector('[data-testid="probe"]')!
    expect(probe.getAttribute('data-customer')).toBe('')
    expect(probe.getAttribute('data-loading')).toBe('false')
  })
})
