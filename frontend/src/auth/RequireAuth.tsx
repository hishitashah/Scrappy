/** Gate for the pages that need a signed-in user (spec 10.4). */

import { useAuthenticator } from '@aws-amplify/ui-react'
import type { ReactNode } from 'react'
import { Navigate } from 'react-router'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { authStatus } = useAuthenticator((context) => [context.authStatus])

  // Amplify checks stored tokens on load. Rendering the landing page during that moment
  // would flash a signed-out screen at someone who is already signed in.
  if (authStatus === 'configuring') {
    return <div className="min-h-screen bg-cream" aria-busy="true" />
  }

  if (authStatus !== 'authenticated') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
