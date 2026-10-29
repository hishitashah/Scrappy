/**
 * Cognito configuration (spec 10.4).
 *
 * These two ids are public by design: the client has no secret, and the id ends up in the
 * built JavaScript either way. Security comes from the user pool, not from hiding them.
 */

import { Amplify } from 'aws-amplify'

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID

export function configureAuth(): void {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: { email: true },
        // Mirrors the pool's own policy (US-1) so the form objects before submitting
        // rather than after a round trip. Cognito still enforces it server-side.
        passwordFormat: {
          minLength: 8,
          requireLowercase: true,
          requireUppercase: true,
          requireNumbers: true,
          requireSpecialCharacters: false,
        },
      },
    },
  })
}
