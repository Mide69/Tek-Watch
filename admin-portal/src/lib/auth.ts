/**
 * Admin Portal Cognito authentication using AWS Amplify v6.
 * Admin pool uses email + password + TOTP MFA.
 */
import { Amplify } from 'aws-amplify'
import {
  signIn,
  signOut,
  confirmSignIn,
  fetchAuthSession,
  type SignInOutput,
} from 'aws-amplify/auth'

let _configured = false

export function configureAmplify() {
  if (_configured) return
  const region   = process.env.NEXT_PUBLIC_COGNITO_REGION    || 'eu-west-2'
  const poolId   = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID  || ''
  const clientId = process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID || ''

  if (!poolId || !clientId) return  // dev mode — skip

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId:       poolId,
        userPoolClientId: clientId,
        loginWith: { email: true },
        mfa: { status: 'on', totpEnabled: true },
      },
    },
  })
  _configured = true
}

export interface AdminUser {
  email: string
  idToken: string
}

/** Step 1: email + password. Returns true if MFA challenge follows. */
export async function adminSignIn(
  email: string,
  password: string
): Promise<{ mfaRequired: boolean; signInOutput?: SignInOutput }> {
  const poolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''

  // Dev mode — no Cognito configured
  if (!poolId) {
    if (!email || !password) throw new Error('Email and password are required')
    localStorage.setItem('tw_admin_token', `mock.${btoa(email)}.sig`)
    return { mfaRequired: false }
  }

  const result = await signIn({ username: email, password })
  const step = result.nextStep?.signInStep

  if (step === 'CONFIRM_SIGN_IN_WITH_TOTP_CODE' || step === 'CONFIRM_SIGN_IN_WITH_SOFTWARE_TOKEN_MFA_CODE') {
    return { mfaRequired: true, signInOutput: result }
  }

  if (step === 'DONE') {
    const session = await fetchAuthSession()
    const token = session.tokens?.idToken?.toString() ?? ''
    localStorage.setItem('tw_admin_token', token)
    return { mfaRequired: false }
  }

  throw new Error(`Unexpected auth step: ${step}`)
}

/** Step 2: confirm TOTP MFA code. */
export async function adminConfirmMfa(code: string): Promise<void> {
  const result = await confirmSignIn({ challengeResponse: code })
  if (result.nextStep?.signInStep !== 'DONE') {
    throw new Error(`Unexpected step after MFA: ${result.nextStep?.signInStep}`)
  }
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString() ?? ''
  localStorage.setItem('tw_admin_token', token)
}

export async function adminSignOut(): Promise<void> {
  const poolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID || ''
  if (poolId) await signOut()
  localStorage.removeItem('tw_admin_token')
}

export function getAdminToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('tw_admin_token')
}
