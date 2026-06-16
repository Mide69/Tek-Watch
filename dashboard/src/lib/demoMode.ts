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
