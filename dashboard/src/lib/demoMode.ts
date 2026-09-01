/**
 * Single source of truth for "are we running without a real Cognito pool?"
 *
 * Demo mode is active when NEXT_PUBLIC_DEMO_MODE is explicitly set, or when
 * the Cognito user pool ID env var is empty / a placeholder value. Placeholder
 * values are matched case-insensitively — CI build validation jobs and local
 * .env files have used different casings (e.g. "PLACEHOLDER" vs "placeholder"),
 * and a case-sensitive check here previously caused the placeholder-pool build
 * to be treated as a real pool, redirecting every page to /login.
 */
const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''

export const isDemoMode = (): boolean => (
  process.env.NEXT_PUBLIC_DEMO_MODE === 'true' ||
  COGNITO_POOL.length === 0 ||
  COGNITO_POOL.toLowerCase().includes('placeholder') ||
  COGNITO_POOL === 'undefined'
)

/**
 * A visitor-opted demo session, separate from the build-time flag above.
 *
 * isDemoMode() is decided at build time and is all-or-nothing: turning it off
 * to enable real Cognito login also removed the "try it without signing up"
 * experience, so every "Launch Live Demo" call to action on the landing page
 * bounced straight to /login — while the page still promised "no signup or
 * credit card needed".
 *
 * This lets both exist. A visitor arriving with ?demo=1 gets a session flag,
 * useAuth skips the login redirect, and useData's existing behaviour does the
 * rest: its apiFetch already falls back to mock data whenever a request fails,
 * so the unauthenticated 401s render the sample dashboard with no extra work.
 *
 * Deliberately NOT a way around authentication: it grants no token and the API
 * still rejects every call. It only decides whether we show mock data instead
 * of redirecting.
 */
const DEMO_SESSION_KEY = 'tw_demo_session'

export const isDemoSession = (): boolean => {
  if (typeof window === 'undefined') return false
  try {
    if (new URLSearchParams(window.location.search).has('demo')) {
      window.localStorage.setItem(DEMO_SESSION_KEY, '1')
      return true
    }
    return window.localStorage.getItem(DEMO_SESSION_KEY) === '1'
  } catch {
    // Private browsing or blocked storage — fall back to the URL alone so the
    // demo still works for that visit.
    try {
      return new URLSearchParams(window.location.search).has('demo')
    } catch {
      return false
    }
  }
}

export const endDemoSession = (): void => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(DEMO_SESSION_KEY)
  } catch {
    /* nothing to clear */
  }
}

/**
 * True when this view is meant to show the sample fixtures rather than the
 * customer's own data — a build with no Cognito at all, or a visitor who
 * opted into the demo.
 *
 * Everything that has to tell "demo" from "a real account with nothing yet"
 * asks this one function. They were briefly asking different questions:
 * apiFetch checked both conditions while the agent page checked only the
 * session, so a dev build served fixtures on every page and "no agent
 * connected" on one.
 */
export const isFixtureView = (): boolean => isDemoMode() || isDemoSession()
