/**
 * @jest-environment jsdom
 */
/**
 * The separation between the demo estate and a real account.
 *
 * Every case here is something that reached production: a deployment with no
 * Cognito silently becoming a demo, and a signed-in customer still being
 * treated as a demo visitor because nothing ever cleared the flag.
 */

const TOKEN_KEY = 'tek_watch_token'
const DEMO_KEY = 'tw_demo_session'

function load(env: Record<string, string | undefined>, href = 'https://app.tekwatch.io/overview') {
  jest.resetModules()
  for (const [k, v] of Object.entries(env)) {
    if (v === undefined) delete process.env[k]
    else process.env[k] = v
  }
  // jsdom cannot navigate, so the location is replaced wholesale.
  delete (window as unknown as Record<string, unknown>).location
  ;(window as unknown as Record<string, unknown>).location = new URL(href) as unknown as Location
  return require('../demoMode')
}

const REAL_POOL = { NEXT_PUBLIC_COGNITO_USER_POOL_ID: 'eu-west-2_real', NEXT_PUBLIC_DEMO_MODE: undefined }
const NO_POOL = { NEXT_PUBLIC_COGNITO_USER_POOL_ID: '', NEXT_PUBLIC_DEMO_MODE: undefined }

beforeEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
})

describe('a deployment with no Cognito configuration', () => {
  it('is a fault, not a demo', () => {
    // The defect exactly: an empty secret shipped to production, and the app
    // treated the absence as permission to behave like a demo.
    const m = load(NO_POOL)
    expect(m.isMisconfigured()).toBe(true)
    expect(m.isDemoBuild()).toBe(false)
  })

  it('is still a fault when someone opted into the demo', () => {
    const m = load(NO_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    expect(m.isMisconfigured()).toBe(true)
  })

  it('rejects a placeholder pool id the same way as an empty one', () => {
    // CI's validation build uses eu-west-2_PLACEHOLDER. Shipping that to
    // production must not look like a working deployment.
    const m = load({ NEXT_PUBLIC_COGNITO_USER_POOL_ID: 'eu-west-2_PLACEHOLDER' })
    expect(m.hasCognitoConfig()).toBe(false)
    expect(m.isMisconfigured()).toBe(true)
  })
})

describe('a demo build', () => {
  it('has to say so explicitly', () => {
    const m = load({ ...NO_POOL, NEXT_PUBLIC_DEMO_MODE: 'true' })
    expect(m.isDemoBuild()).toBe(true)
    expect(m.isMisconfigured()).toBe(false)
  })

  it('or be a developer on their own machine', () => {
    const m = load(NO_POOL, 'http://localhost:3000/overview')
    expect(m.isDemoBuild()).toBe(true)
    expect(m.isMisconfigured()).toBe(false)
  })
})

describe('an account tab', () => {
  it('is never shown the sample estate', () => {
    // The guarantee the whole module exists for. No demo flag in this tab, so
    // no fixtures, whatever else is lying around.
    const m = load(REAL_POOL)
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    expect(m.isDemoSession()).toBe(false)
    expect(m.isFixtureView()).toBe(false)
  })

  it('ignores a demo flag left in localStorage by an older build', () => {
    // The defect the customer hit: the flag used to live in localStorage,
    // shared by every tab and surviving a browser restart, so a demo tried
    // once followed them into their account indefinitely. Nothing reads that
    // location any more.
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    expect(m.isDemoSession()).toBe(false)
    expect(m.isFixtureView()).toBe(false)
  })

  it('does not inherit a demo opened in a different tab', () => {
    // sessionStorage is per tab. Simulating the other tab by writing the flag
    // to localStorage, which is the only storage the two would share.
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')

    expect(m.isFixtureView()).toBe(false)
  })
})

describe('a demo tab', () => {
  it('shows the sample estate even to someone signed in', () => {
    // Deliberate: you should be able to look at the demo without signing out.
    // It stays in this tab, so their account tab is unaffected.
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    expect(m.isDemoSession()).toBe(true)
    expect(m.isFixtureView()).toBe(true)
  })

  it('remembers across pages within that tab', () => {
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    expect(m.isDemoSession()).toBe(true)

    const same = load(REAL_POOL, 'https://app.tekwatch.io/cost')
    expect(same.isDemoSession()).toBe(true)
  })

  it('does not write the flag anywhere other tabs can see', () => {
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    m.isDemoSession()

    expect(window.sessionStorage.getItem(DEMO_KEY)).toBe('1')
    expect(window.localStorage.getItem(DEMO_KEY)).toBeNull()
  })
})

describe('leaving the demo', () => {
  it('ends it, and clears the older localStorage flag too', () => {
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    m.isDemoSession()
    window.localStorage.setItem(DEMO_KEY, '1') // as an older build would have left it

    m.endDemoSession()

    expect(window.sessionStorage.getItem(DEMO_KEY)).toBeNull()
    expect(window.localStorage.getItem(DEMO_KEY)).toBeNull()
  })
})

describe('the viewer can change after first paint', () => {
  it('tells subscribers when a demo ends', () => {
    // Components resolve the viewer once, in an effect. useAuth confirms a
    // Cognito session after that has already run, so without a notification the
    // first, stale answer stood for the rest of the page's life: the demo badge
    // stayed up on a signed-in account, security showed fixture IAM figures, and
    // the agent page hid the download button behind "not this demo".
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    m.isDemoSession()

    let told = 0
    const stop = m.subscribeViewer(() => { told += 1 })

    m.endDemoSession()

    expect(told).toBe(1)
    expect(window.sessionStorage.getItem(DEMO_KEY)).toBeNull()
    stop()
  })

  it('stops telling a subscriber that has unsubscribed', () => {
    const m = load(REAL_POOL)
    let told = 0
    const stop = m.subscribeViewer(() => { told += 1 })
    stop()

    m.endDemoSession()

    expect(told).toBe(0)
  })

  it('reports a real account once the demo has ended', () => {
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    expect(m.isFixtureView()).toBe(true)

    m.endDemoSession()
    expect(window.sessionStorage.getItem(DEMO_KEY)).toBeNull()

    // Exit demo navigates away, so the next page has no ?demo in the url. The
    // real code also strips the param in place, but jsdom's location is a stub
    // here and history.replaceState cannot touch it, so the navigation is what
    // this asserts.
    const after = load(REAL_POOL, 'https://app.tekwatch.io/overview')
    expect(after.isFixtureView()).toBe(false)
  })
})
