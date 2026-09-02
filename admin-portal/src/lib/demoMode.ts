/**
 * Single source of truth for demo-mode detection in the admin portal.
 * Mirrors dashboard/src/lib/demoMode.ts so both apps behave identically.
 *
 * Demo mode = no real Cognito/backend available, so auth is bypassed and the
 * API client returns mock data (see lib/api.ts + lib/demoData.ts). This is what
 * lets the admin portal run as a zero-cost static demo on Vercel with no AWS.
 */
const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''

/** A pool id that is present and is not a CI placeholder. */
const hasCognitoConfig = (): boolean => {
  const pool = COGNITO_POOL.trim()
  if (!pool || pool === 'undefined') return false
  return !pool.toLowerCase().includes('placeholder')
}

/**
 * A real user pool settles it, whatever else the environment claims.
 *
 * A committed .env.production set NEXT_PUBLIC_DEMO_MODE=true for a Vercel demo
 * and was loaded by every production build. On the customer dashboard that
 * shipped the live site as a demo. This console was spared only because its
 * sign-in path checks the pool separately — which is luck, not design, and on
 * a console with account-wide reach that is not good enough.
 *
 * Contradictory configuration now resolves towards "this is real". The cost of
 * being wrong that way is an admin who has to sign in; the cost of being wrong
 * the other way is an admin console that does not ask.
 */
export const isDemoMode = (): boolean => {
  if (hasCognitoConfig()) return false
  return process.env.NEXT_PUBLIC_DEMO_MODE === 'true' || !hasCognitoConfig()
}
