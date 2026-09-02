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

/**
 * The demo lives in sessionStorage, so it belongs to one browser tab.
 *
 * It used to live in localStorage, which is shared by every tab and survives
 * the browser closing. So a visitor who tried the demo once carried the flag
 * into their account weeks later: the demo badge on a signed-in dashboard,
 * sample security figures, and the agent page hiding its download button
 * behind "available on a real account, not this demo".
 *
 * Per-tab is the separation the product actually wants. A demo tab shows the
 * sample estate even to someone signed in, which is the point — you should be
 * able to look at the demo without signing out. Their account tab never has
 * the flag, so it can never show fixtures. Closing the tab ends the demo, and
 * so does Exit demo.
 */
function demoStore(): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

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
  // A real user pool settles it, whatever else the environment claims.
  //
  // dashboard/.env.production is committed and sets NEXT_PUBLIC_DEMO_MODE=true,
  // for the zero-cost Vercel demo. Next.js loads that file for every production
  // build, and the deploy workflow overrode the pool and client id but not the
  // demo flag — so every build shipped to app.tekwatch.io was a demo build.
  // That is the whole of it: the badge over a signed-in dashboard, fixtures on
  // a live account, a hidden download button, and "Back to Home" in place of
  // Sign out.
  //
  // Configuration that contradicts itself now resolves towards "this is real",
  // because being wrong in that direction shows a customer an empty dashboard,
  // and being wrong in the other shows them somebody else's data.
  if (hasCognitoConfig()) return false
  if (process.env.NEXT_PUBLIC_DEMO_MODE === 'true') return true
  return onLocalhost()
}

/**
 * A deployed build with no usable Cognito configuration.
 *
 * Not a demo — a broken deployment. Callers surface it rather than working
 * around it, because the alternative is an authentication gate that isn't one.
 */
export const isMisconfigured = (): boolean =>
  !hasCognitoConfig() && !isDemoBuild()

/** Is there a stored session token? Exported: useAuth has to ask the same
 *  question, and two implementations of "are they signed in" is how the demo
 *  and the account got tangled in the first place. */
export function hasSession(): boolean {
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

  let onDemoUrl = false
  try {
    onDemoUrl = new URLSearchParams(window.location.search).has('demo')
  } catch {
    onDemoUrl = false
  }

  const store = demoStore()
  if (!store) return onDemoUrl // private browsing: the url alone drives it

  if (onDemoUrl) {
    store.setItem(DEMO_SESSION_KEY, '1')
    return true
  }
  return store.getItem(DEMO_SESSION_KEY) === '1'
}

export const endDemoSession = (): void => {
  demoStore()?.removeItem(DEMO_SESSION_KEY)

  // Take ?demo=1 out of the address bar as well. isDemoSession reads the url
  // first, so leaving it there would re-arm the demo on the very next read and
  // Exit demo would appear to do nothing.
  try {
    const url = new URL(window.location.href)
    if (url.searchParams.has('demo')) {
      url.searchParams.delete('demo')
      window.history.replaceState({}, '', url.toString())
    }
  } catch {
    /* no history api, or a url we cannot parse */
  }
  // Older builds put this in localStorage, where it outlived the browser
  // closing. Clear that too, or anyone carrying one stays in the demo forever.
  try {
    window.localStorage.removeItem(DEMO_SESSION_KEY)
  } catch {
    /* nothing to clear */
  }
  notifyViewerChanged()
}

/**
 * Who is viewing can change after first paint.
 *
 * Components resolve it once in an effect, which was right when the answer was
 * fixed for the life of the page. It is not: useAuth confirms a Cognito session
 * asynchronously, and a demo flag left in local storage from an earlier visit
 * is still set while that happens. Anything that had already asked kept the
 * stale answer for the rest of the page's life — which is why a signed-in
 * customer saw the demo badge, sample IAM figures, and an agent page that hid
 * the download button behind "not this demo".
 *
 * So the answer is published rather than sampled: clearing a demo session
 * tells everyone who asked.
 */
const viewerListeners = new Set<() => void>()

export function subscribeViewer(listener: () => void): () => void {
  viewerListeners.add(listener)
  return () => { viewerListeners.delete(listener) }
}

export function notifyViewerChanged(): void {
  viewerListeners.forEach(listener => listener())
}

/**
 * Should this view show the sample estate?
 *
 * The single question every component asks. A signed-in customer is never
 * inside it, which is the property the whole module exists to guarantee.
 */
export const isFixtureView = (): boolean => isDemoBuild() || isDemoSession()
