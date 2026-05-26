/**
 * Cognito authentication helpers using AWS Amplify v6.
 *
 * Wraps Amplify Auth so the rest of the app never imports Amplify directly.
 */
import { Amplify } from 'aws-amplify'
import {
  signIn,
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
 * Sign in with Customer ID (username) and password.
 * Returns the authenticated user with JWT id token.
 */
export async function authSignIn(customerId: string, password: string): Promise<AuthUser> {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''

  // Dev mode — mock auth when Cognito is not configured
  if (!userPoolId) {
    if (!customerId.match(/^TT-\d{4}$/)) {
      throw new Error('Invalid Customer ID format. Expected: TT-XXXX')
    }
    if (!password) throw new Error('Password is required')
    // Return a mock token for local development
    const mockToken = btoa(JSON.stringify({ sub: customerId, 'cognito:username': customerId, email: '' }))
    return { customerId, email: '', idToken: `mock.${mockToken}.sig` }
  }

  const input: SignInInput = { username: customerId, password }
  const result = await signIn(input)

  if (result.nextStep?.signInStep !== 'DONE') {
    throw new Error(`Unexpected auth step: ${result.nextStep?.signInStep}`)
  }

  const session = await fetchAuthSession()
  const idToken = session.tokens?.idToken?.toString() ?? ''
  const payload = session.tokens?.idToken?.payload ?? {}

  return {
    customerId: (payload['cognito:username'] as string) || customerId,
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
