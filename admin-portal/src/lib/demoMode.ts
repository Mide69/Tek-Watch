/**
 * Single source of truth for demo-mode detection in the admin portal.
 * Mirrors dashboard/src/lib/demoMode.ts so both apps behave identically.
 *
 * Demo mode = no real Cognito/backend available, so auth is bypassed and the
 * API client returns mock data (see lib/api.ts + lib/demoData.ts). This is what
 * lets the admin portal run as a zero-cost static demo on Vercel with no AWS.
 */
const COGNITO_POOL = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''

export const isDemoMode = (): boolean =>
  process.env.NEXT_PUBLIC_DEMO_MODE === 'true' ||
  COGNITO_POOL.length === 0 ||
  COGNITO_POOL.toLowerCase().includes('placeholder') ||
  COGNITO_POOL === 'undefined'
