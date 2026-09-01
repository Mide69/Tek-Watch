/**
 * Admin Portal Cognito authentication using AWS Amplify v6.
 * Admin pool uses email + password + TOTP MFA.
 *
 * Cognito sign-in is a state machine, not a single call. A brand-new admin
 * created with admin-create-user walks through:
 *
 *   signIn -> NEW_PASSWORD_REQUIRED   (user starts in FORCE_CHANGE_PASSWORD)
 *          -> TOTP_SETUP              (MFA is mandatory, nothing enrolled yet)
 *          -> DONE
 *
 * while an already-onboarded admin walks through:
 *
 *   signIn -> TOTP_CODE -> DONE
 *
 * Only the second path used to be implemented, so the first admin could never
 * sign in at all — every unhandled step threw "Unexpected auth step". Each call
 * below returns the NEXT step rather than assuming one, so the caller can drive
 * the machine to DONE however many hops it takes.
 */
import { Amplify } from 'aws-amplify'
import {
  signIn,
  signOut,
  confirmSignIn,
  fetchAuthSession,
  resetPassword,
  confirmResetPassword,
  type SignInOutput,
  type ConfirmSignInOutput,
} from 'aws-amplify/auth'
import { isDemoMode } from './demoMode'

let _configured = false

export function configureAmplify() {
  if (_configured) return
  if (isDemoMode()) return // demo/dev — no real Cognito to configure
  const region = process.env.NEXT_PUBLIC_COGNITO_REGION || 'eu-west-2'
  const poolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
  const clientId = process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID || ''

  if (!poolId || !clientId) return // dev mode — skip

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: poolId,
        userPoolClientId: clientId,
        loginWith: { email: true },
        mfa: { status: 'on', totpEnabled: true },
      },
    },
  })
  _configured = true
  void region // region is carried by the pool id; kept for clarity/config parity
}

export interface AdminUser {
  email: string
  idToken: string
}

/**
 * Where the sign-in machine currently stands. The caller renders a different
 * form per `kind` and feeds the answer back through `adminRespond`.
 */
export type AdminAuthStep =
  | { kind: 'DONE' }
  | { kind: 'NEW_PASSWORD_REQUIRED' }
  | { kind: 'TOTP_SETUP'; secret: string; setupUri: string }
  | { kind: 'TOTP_CODE' }
  // An operator ran admin-reset-user-password, so the account sits in
  // RESET_REQUIRED. Cognito has already emailed a code; the caller should send
  // the user to the forgot-password confirmation screen rather than error out.
  | { kind: 'RESET_REQUIRED' }

type AmplifySignInResult = SignInOutput | ConfirmSignInOutput

function persistSession(token: string) {
  localStorage.setItem('tw_admin_token', token)
}

async function finishSession(): Promise<AdminAuthStep> {
  const session = await fetchAuthSession()
  const idToken = session.tokens?.idToken?.toString()

  // Fail loudly rather than storing "". An empty token was persisted, DONE was
  // reported, the caller redirected to /customers, and useAdminAuth then read a
  // falsy token and sent the user back to /login — a silent loop that looks
  // like the password was wrong, with nothing in the UI to explain it.
  if (!idToken) {
    throw new Error(
      'Signed in, but no session token was returned. Please try again.'
    )
  }

  persistSession(idToken)
  return { kind: 'DONE' }
}

/** Translate an Amplify result into our step, finalising the session on DONE. */
async function toStep(result: AmplifySignInResult): Promise<AdminAuthStep> {
  const next = result.nextStep

  switch (next.signInStep) {
    case 'DONE':
      return finishSession()

    case 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED':
      return { kind: 'NEW_PASSWORD_REQUIRED' }

    case 'CONTINUE_SIGN_IN_WITH_TOTP_SETUP': {
      const details = next.totpSetupDetails
      return {
        kind: 'TOTP_SETUP',
        secret: details.sharedSecret,
        // Rendered as a link and as the raw secret; authenticator apps accept
        // either the otpauth:// URI or manual entry of the secret.
        setupUri: details.getSetupUri('Tek Watch Admin').toString(),
      }
    }

    case 'CONFIRM_SIGN_IN_WITH_TOTP_CODE':
      return { kind: 'TOTP_CODE' }

    case 'RESET_PASSWORD':
      return { kind: 'RESET_REQUIRED' }

    default:
      throw new Error(`Unsupported auth step: ${next.signInStep}`)
  }
}

/** Step 1: email + password. Returns whatever Cognito wants next. */
/**
 * True only on a developer's own machine, or a build that explicitly declared
 * itself a demo. A deployed build must have real Cognito configuration.
 */
function isLocalDevelopment(): boolean {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === 'true') return true
  if (typeof window === 'undefined') return true // build-time prerender, never a user
  const { hostname } = window.location
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname.endsWith('.local')
}

/**
 * True when Cognito refused a sign-in because a session already exists.
 *
 * Amplify keeps its own tokens in local storage, separate from the id token
 * this app stores. They fall out of step easily: a half-finished first login,
 * a cleared app token, an expired session, or simply opening the login page
 * while still signed in. In every one of those cases signIn throws "There is
 * already a signed in user" before it ever reaches Cognito, which reads to the
 * operator as a rejected password on a password they typed correctly.
 */
function isAlreadySignedIn(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const { name, message } = error as { name?: string; message?: string }
  return (
    name === 'UserAlreadyAuthenticatedException' ||
    (message ?? '').toLowerCase().includes('already a signed in user')
  )
}

/**
 * Sign in, clearing any stale Amplify session first if one is in the way.
 *
 * Signing out and retrying is the right call rather than reusing the existing
 * session: someone has just typed an email and password, so they mean to start
 * a fresh session as that user, who may not be the one still signed in.
 */
async function signInFresh(input: { username: string; password: string }) {
  try {
    return await signIn(input)
  } catch (error) {
    if (!isAlreadySignedIn(error)) throw error
    try {
      await signOut()
    } catch {
      // Best effort: if the stale session cannot be cleared cleanly, the retry
      // below will surface the real problem rather than this one.
    }
    return signIn(input)
  }
}

export async function adminSignIn(email: string, password: string): Promise<AdminAuthStep> {
  // Demo/dev mode — no Cognito. Any credentials grant a mock session so the
  // demo is explorable; the placeholder pool id also routes here (not just an
  // empty one), matching isDemoMode()'s logic.
  if (isDemoMode()) {
    // Same guard as the customer dashboard, and it matters more here: this
    // console has account-wide reach. isDemoMode() is true whenever the pool id
    // is missing or a placeholder, so an admin build shipped without its
    // secrets would accept any email and any password. The pool is configured
    // today; this makes a future missing secret a locked door rather than an
    // open one.
    if (!isLocalDevelopment()) {
      throw new Error(
        'Sign-in is unavailable: this deployment is missing its Cognito configuration.'
      )
    }
    if (!email || !password) throw new Error('Email and password are required')
    persistSession(`mock.${btoa(email)}.sig`)
    return { kind: 'DONE' }
  }

  return toStep(await signInFresh({ username: email, password }))
}

/**
 * Answer the current challenge — a new password, a TOTP code during setup, or
 * a TOTP code at normal sign-in. Cognito distinguishes them by the pending
 * challenge, so one call covers all three. Returns the step after this one,
 * since answering rarely lands straight on DONE for a new user.
 */
export async function adminRespond(challengeResponse: string): Promise<AdminAuthStep> {
  return toStep(await confirmSignIn({ challengeResponse }))
}

/**
 * Start a forgot-password reset. Cognito emails a numeric CODE, not a link —
 * the caller must collect that code and call adminConfirmForgotPassword.
 *
 * Deliberately does not reveal whether the account exists: Cognito throws
 * UserNotFoundException, which we swallow so the UI can show the same
 * "check your email" message either way and not leak valid admin addresses.
 */
export async function adminForgotPassword(email: string): Promise<void> {
  if (isDemoMode()) return
  try {
    await resetPassword({ username: email })
  } catch (err) {
    const name = (err as { name?: string })?.name
    if (name === 'UserNotFoundException' || name === 'InvalidParameterException') return
    throw err
  }
}

/** Complete the reset with the emailed code and a new password. */
export async function adminConfirmForgotPassword(
  email: string,
  code: string,
  newPassword: string
): Promise<void> {
  if (isDemoMode()) return
  await confirmResetPassword({ username: email, confirmationCode: code, newPassword })
}

export async function adminSignOut(): Promise<void> {
  if (!isDemoMode()) await signOut()
  localStorage.removeItem('tw_admin_token')
}

/**
 * Email of the signed-in admin, read from the ID token.
 *
 * The sidebar previously hardcoded "admin@tektribe.io" — an address on an
 * unregistered domain, shown regardless of who was actually signed in. Decoding
 * the token is display-only; Cognito has already validated it, and the API
 * re-verifies on every request, so nothing is trusted on the strength of this.
 */
export function getAdminEmail(): string | null {
  const token = getAdminToken()
  if (!token) return null
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const claims = JSON.parse(json) as { email?: string }
    return claims.email ?? null
  } catch {
    return null
  }
}

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('tw_admin_token')
}
