/**
 * Sign-in flow tests.
 *
 * Both cases here were live defects that presented as a rejected password on a
 * password the customer had typed correctly.
 */

const signIn = jest.fn()
const signOut = jest.fn()
const confirmSignIn = jest.fn()
const fetchAuthSession = jest.fn()

jest.mock('aws-amplify', () => ({ Amplify: { configure: jest.fn() } }))
jest.mock('aws-amplify/auth', () => ({
  signIn: (...args: unknown[]) => signIn(...args),
  signOut: (...args: unknown[]) => signOut(...args),
  confirmSignIn: (...args: unknown[]) => confirmSignIn(...args),
  fetchAuthSession: (...args: unknown[]) => fetchAuthSession(...args),
  getCurrentUser: jest.fn(),
  resetPassword: jest.fn(),
  confirmResetPassword: jest.fn(),
}))

import { authSignIn } from '@/lib/auth'

const SESSION = {
  tokens: {
    idToken: {
      toString: () => 'id-token',
      payload: { 'cognito:username': 'TT-0001', email: 'a@b.com' },
    },
  },
}

beforeEach(() => {
  jest.clearAllMocks()
  // authSignIn short-circuits to mock auth when no pool is configured. It reads
  // this inside the call, so setting it here is enough.
  process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID = 'eu-west-2_test'
  process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID = 'test-client'
  fetchAuthSession.mockResolvedValue(SESSION)
})

describe('authSignIn', () => {
  it('returns the user on a clean sign-in', async () => {
    signIn.mockResolvedValue({ nextStep: { signInStep: 'DONE' } })

    const result = await authSignIn('TT-0001', 'pw')

    expect(result).toEqual({ status: 'DONE', user: expect.objectContaining({ idToken: 'id-token' }) })
    expect(signOut).not.toHaveBeenCalled()
  })

  it('reports the first-login challenge instead of throwing', async () => {
    // Signup leaves the account in FORCE_CHANGE_PASSWORD. This used to throw
    // "Unexpected auth step", so no new customer could ever get in.
    signIn.mockResolvedValue({
      nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED' },
    })

    await expect(authSignIn('TT-0001', 'temp-pw')).resolves.toEqual({
      status: 'NEW_PASSWORD_REQUIRED',
    })
  })

  it('clears a stale Amplify session and retries', async () => {
    // Amplify holds its own tokens. When they outlive the app's, signIn refuses
    // with "There is already a signed in user" before reaching Cognito, and the
    // customer sees that in place of a login.
    const stale = Object.assign(new Error('There is already a signed in user.'), {
      name: 'UserAlreadyAuthenticatedException',
    })
    signIn
      .mockRejectedValueOnce(stale)
      .mockResolvedValueOnce({ nextStep: { signInStep: 'DONE' } })

    const result = await authSignIn('TT-0001', 'pw')

    expect(signOut).toHaveBeenCalledTimes(1)
    expect(signIn).toHaveBeenCalledTimes(2)
    expect(result.status).toBe('DONE')
  })

  it('retries even when signing the stale session out fails', async () => {
    const stale = Object.assign(new Error('There is already a signed in user.'), {
      name: 'UserAlreadyAuthenticatedException',
    })
    signIn
      .mockRejectedValueOnce(stale)
      .mockResolvedValueOnce({ nextStep: { signInStep: 'DONE' } })
    signOut.mockRejectedValue(new Error('network'))

    await expect(authSignIn('TT-0001', 'pw')).resolves.toEqual(
      expect.objectContaining({ status: 'DONE' }),
    )
  })

  it('does not swallow a genuinely wrong password', async () => {
    // The retry must be scoped to the stale-session case. Retrying a bad
    // password would burn a second attempt against Cognito's lockout counter.
    const wrong = Object.assign(new Error('Incorrect username or password.'), {
      name: 'NotAuthorizedException',
    })
    signIn.mockRejectedValue(wrong)

    await expect(authSignIn('TT-0001', 'wrong')).rejects.toThrow('Incorrect username or password.')
    expect(signIn).toHaveBeenCalledTimes(1)
    expect(signOut).not.toHaveBeenCalled()
  })

  it('refuses to report success without a token', async () => {
    // An empty idToken was previously returned as a successful login; callers
    // stored it and the customer was bounced back to /login with no reason.
    signIn.mockResolvedValue({ nextStep: { signInStep: 'DONE' } })
    fetchAuthSession.mockResolvedValue({ tokens: undefined })

    await expect(authSignIn('TT-0001', 'pw')).rejects.toThrow(/no session token/i)
  })
})
