/** Thin wrappers over Amplify, so the rest of the app imports one small module. */

import { fetchAuthSession, signOut as amplifySignOut } from 'aws-amplify/auth'

/**
 * The current access token, or null when signed out.
 *
 * `fetchAuthSession` refreshes an expired access token from the 30-day refresh token by
 * itself, which is what makes "the session survives a refresh and lasts up to 30 days"
 * (US-2) true without any code of ours.
 */
export async function accessToken(): Promise<string | null> {
  try {
    const session = await fetchAuthSession()
    return session.tokens?.accessToken?.toString() ?? null
  } catch {
    // Not signed in, or the refresh token has expired: both mean "no token".
    return null
  }
}

export async function signOut(): Promise<void> {
  await amplifySignOut()
}
