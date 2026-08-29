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

type AmplifySignInResult = SignInOutput | ConfirmSignInOutput

function persistSession(token: string) {
  localStorage.setItem('tw_admin_token', token)
}

async function finishSession(): Promise<AdminAuthStep> {
  const session = await fetchAuthSession()
  persistSession(session.tokens?.idToken?.toString() ?? '')
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

    default:
      throw new Error(`Unsupported auth step: ${next.signInStep}`)
  }
}

/** Step 1: email + password. Returns whatever Cognito wants next. */
export async function adminSignIn(email: string, password: string): Promise<AdminAuthStep> {
  // Demo/dev mode — no Cognito. Any credentials grant a mock session so the
  // demo is explorable; the placeholder pool id also routes here (not just an
  // empty one), matching isDemoMode()'s logic.
  if (isDemoMode()) {
    if (!email || !password) throw new Error('Email and password are required')
    persistSession(`mock.${btoa(email)}.sig`)
    return { kind: 'DONE' }
  }

  return toStep(await signIn({ username: email, password }))
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

export async function adminSignOut(): Promise<void> {
  if (!isDemoMode()) await signOut()
  localStorage.removeItem('tw_admin_token')
}

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('tw_admin_token')
}
