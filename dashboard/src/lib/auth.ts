/**
 * Cognito authentication helpers using AWS Amplify v6.
 *
 * Wraps Amplify Auth so the rest of the app never imports Amplify directly.
 */
import { Amplify } from 'aws-amplify'
import {
  signIn,
  confirmSignIn,
  signOut,
  getCurrentUser,
  fetchAuthSession,
  resetPassword,
  confirmResetPassword,
  type SignInInput,
} from 'aws-amplify/auth'

// Configure Amplify once — safe to call multiple times (idempotent)
export function configureAmplify() {
  const region = process.env.NEXT_PUBLIC_COGNITO_REGION || 'eu-west-2'
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
  const clientId = process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID || ''

  if (!userPoolId || !clientId) {
    // Dev mode — skip Amplify config, use mock auth
    return
  }

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId: clientId,
        loginWith: { username: true },
      },
    },
  })
}

export interface AuthUser {
  customerId: string
  email: string
  idToken: string
}

/**
 * Result of a sign-in attempt.
 *
 * Cognito sign-in is a state machine, not a single call. A customer created by
 * signup arrives in FORCE_CHANGE_PASSWORD and must choose their own password
 * before any token is issued, so the first sign-in takes two steps.
 *
 * This previously threw "Unexpected auth step" on anything but DONE, which
 * meant every newly signed-up customer received an invite email, entered the
 * right credentials, and was told something had gone wrong.
 */
export type AuthResult =
  | { status: 'DONE'; user: AuthUser }
  | { status: 'NEW_PASSWORD_REQUIRED' }

/**
 * Sign in with Customer ID (username) and password.
 * Returns either the authenticated user or the next step Cognito requires.
 */
export async function authSignIn(customerId: string, password: string): Promise<AuthResult> {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''

  // Dev mode — mock auth when Cognito is not configured
  if (!userPoolId) {
    // Ids are random base32 now (TT-9F4KQ7M2), not a 4-digit counter. The old
    // /^TT-\d{4}$/ would reject every id the platform currently mints.
    if (!customerId.match(/^TT-[0-9A-Z]{4,}$/i)) {
      throw new Error('Invalid Customer ID format. Expected: TT-XXXXXXXX')
    }
    if (!password) throw new Error('Password is required')
    // Return a mock token for local development
    const mockToken = btoa(JSON.stringify({ sub: customerId, 'cognito:username': customerId, email: '' }))
    return { status: 'DONE', user: { customerId, email: '', idToken: `mock.${mockToken}.sig` } }
  }

  const input: SignInInput = { username: customerId, password }
  const result = await signIn(input)
  const step = result.nextStep?.signInStep

  if (step === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
    return { status: 'NEW_PASSWORD_REQUIRED' }
  }
  if (step !== 'DONE') {
    throw new Error(`Unsupported auth step: ${step}`)
  }

  return { status: 'DONE', user: await currentUserFromSession(customerId) }
}

/**
 * Complete a first sign-in by setting the customer's own password.
 * Cognito distinguishes this by the pending challenge, so no extra context
 * needs carrying between the two calls.
 */
export async function authCompleteNewPassword(
  customerId: string,
  newPassword: string
): Promise<AuthUser> {
  const result = await confirmSignIn({ challengeResponse: newPassword })
  if (result.nextStep?.signInStep !== 'DONE') {
    throw new Error(`Unsupported step after setting password: ${result.nextStep?.signInStep}`)
  }
  return currentUserFromSession(customerId)
}

async function currentUserFromSession(fallbackId: string): Promise<AuthUser> {
  const session = await fetchAuthSession()
  const idToken = session.tokens?.idToken?.toString()

  // Fail loudly rather than returning an empty token. An empty string reads as
  // a successful sign-in to callers, which then store it and bounce the user
  // back to /login with no explanation.
  if (!idToken) {
    throw new Error('Signed in, but no session token was returned. Please try again.')
  }

  const payload = session.tokens?.idToken?.payload ?? {}
  return {
    customerId: (payload['cognito:username'] as string) || fallbackId,
    email: (payload['email'] as string) || '',
    idToken,
  }
}

/**
 * Sign out the current user and clear local storage.
 */
export async function authSignOut(): Promise<void> {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
  if (!userPoolId) {
    localStorage.removeItem('tek_watch_token')
    localStorage.removeItem('tek_watch_customer_id')
    return
  }
  await signOut()
  localStorage.removeItem('tek_watch_token')
  localStorage.removeItem('tek_watch_customer_id')
}

/**
 * Get the current authenticated user, or null if not signed in.
 */
export async function getAuthUser(): Promise<AuthUser | null> {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''

  // Dev mode
  if (!userPoolId) {
    const token = localStorage.getItem('tek_watch_token')
    const customerId = localStorage.getItem('tek_watch_customer_id')
    if (!token || !customerId) return null
    return { customerId, email: '', idToken: token }
  }

  try {
    const session = await fetchAuthSession()
    if (!session.tokens?.idToken) return null
    const payload = session.tokens.idToken.payload
    return {
      customerId: (payload['cognito:username'] as string) || '',
      email: (payload['email'] as string) || '',
      idToken: session.tokens.idToken.toString(),
    }
  } catch {
    return null
  }
}

/**
 * Initiate forgot-password flow.
 */
export async function authForgotPassword(customerId: string): Promise<void> {
  await resetPassword({ username: customerId })
}

/**
 * Confirm forgot-password with code and new password.
 */
export async function authConfirmForgotPassword(
  customerId: string,
  code: string,
  newPassword: string
): Promise<void> {
  await confirmResetPassword({ username: customerId, confirmationCode: code, newPassword })
}
