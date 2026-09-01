/**
 * Who is looking at this dashboard, and whose data should it show.
 *
 * There are exactly three viewers, and they are mutually exclusive:
 *
 *   1. Demo build    — an explicitly built demo (NEXT_PUBLIC_DEMO_MODE=true),
 *                      or a developer running locally with no Cognito.
 *   2. Demo visitor  — someone who chose "Launch Live Demo" and is NOT signed
 *                      in. They see the sample estate, clearly labelled.
 *   3. Account       — someone signed in. They see their own AWS estate, and
 *                      nothing else, ever. Zeros until their agent reports.
 *
 * The previous model inferred demo-ness from configuration being absent:
 * isDemoMode() meant "no Cognito pool id is set". Two things followed from
 * that, and both reached production.
 *
 * A production build made with an empty COGNITO_CUSTOMER_USER_POOL_ID_PROD
 * secret did not fail — it silently became a demo. Every page served sample
 * data, every visitor was "TT-DEMO", and the login form accepted any
 * credentials, because the sign-in path also treated a missing pool as
 * permission to mock. Nothing anywhere said the deployment was misconfigured.
 *
 * And a signed-in customer could still be treated as a demo visitor, because
 * the demo flag lived in local storage with nothing to clear it. Signing in
 * did not end the demo.
 *
 * So: demo is now declared, never inferred, and it is defined against the
 * session rather than alongside it. Signing in ends a demo. A demo cannot
 * start while signed in. A deployment missing its configuration is a fault to
 * be surfaced, not a mode to fall into.
 */

const DEMO_SESSION_KEY = 'tw_demo_session'
const TOKEN_KEY = 'tek_watch_token'

const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''

/** A pool id that is present and is not a CI placeholder. */
export const hasCognitoConfig = (): boolean => {
  const pool = COGNITO_POOL.trim()
  if (!pool || pool === 'undefined') return false
  return !pool.toLowerCase().includes('placeholder')
}

function onLocalhost(): boolean {
  if (typeof window === 'undefined') return false
  const { hostname } = window.location
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname.endsWith('.local')
}

/**
 * A build that is meant to be a demo. Declared, not inferred.
 *
 * The localhost clause keeps `npm run dev` working without a Cognito pool.
 * It is deliberately scoped to the machine the developer is sitting at, so a
 * deployed build can never qualify by accident.
 */
export const isDemoBuild = (): boolean => {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === 'true') return true
  return !hasCognitoConfig() && onLocalhost()
}

/**
 * A deployed build with no usable Cognito configuration.
 *
 * Not a demo — a broken deployment. Callers surface it rather than working
 * around it, because the alternative is an authentication gate that isn't one.
 */
export const isMisconfigured = (): boolean =>
  !hasCognitoConfig() && !isDemoBuild()

function hasSession(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return !!window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return false
  }
}

/**
 * A visitor exploring the sample estate without an account.
 *
 * Signing in wins, always. If a session exists the demo flag is cleared and
 * this returns false, so a customer can never be shown sample data on the
 * strength of a demo they took before signing up.
 */
export const isDemoSession = (): boolean => {
  if (typeof window === 'undefined') return false

  if (hasSession()) {
    endDemoSession()
    return false
  }

  try {
    if (new URLSearchParams(window.location.search).has('demo')) {
      window.localStorage.setItem(DEMO_SESSION_KEY, '1')
      return true
    }
    return window.localStorage.getItem(DEMO_SESSION_KEY) === '1'
  } catch {
    // Private browsing or blocked storage — fall back to the url alone so the
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
 * Should this view show the sample estate?
 *
 * The single question every component asks. A signed-in customer is never
 * inside it, which is the property the whole module exists to guarantee.
 */
export const isFixtureView = (): boolean => isDemoBuild() || isDemoSession()

/**
 * Retained under its old name because several components still ask it, and it
 * still means the same thing to them: "is this the sample estate rather than
 * a real account?"
 */
export const isDemoMode = (): boolean => isFixtureView()
