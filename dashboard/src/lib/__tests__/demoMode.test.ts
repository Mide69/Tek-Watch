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

describe('a signed-in customer', () => {
  it('is never shown the sample estate', () => {
    // The guarantee the whole module exists for.
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    expect(m.isDemoSession()).toBe(false)
    expect(m.isFixtureView()).toBe(false)
  })

  it('has the stale demo flag cleared, not merely ignored', () => {
    // Ignoring it would leave it to resurface after signing out.
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    m.isDemoSession()

    expect(window.localStorage.getItem(DEMO_KEY)).toBeNull()
  })

  it('stays real even arriving on a ?demo=1 link', () => {
    // Someone forwards a demo link to a customer who is already signed in.
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')

    expect(m.isDemoSession()).toBe(false)
    expect(m.isFixtureView()).toBe(false)
  })
})

describe('a demo visitor', () => {
  it('gets the sample estate from a ?demo=1 link', () => {
    const m = load(REAL_POOL, 'https://app.tekwatch.io/overview?demo=1')
    expect(m.isDemoSession()).toBe(true)
    expect(m.isFixtureView()).toBe(true)
  })

  it('keeps it across pages once opted in', () => {
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    expect(m.isFixtureView()).toBe(true)
  })

  it('loses it the moment a session exists', () => {
    const m = load(REAL_POOL)
    window.localStorage.setItem(DEMO_KEY, '1')
    expect(m.isFixtureView()).toBe(true)

    window.localStorage.setItem(TOKEN_KEY, 'a.real.token')
    expect(m.isFixtureView()).toBe(false)
  })
})
