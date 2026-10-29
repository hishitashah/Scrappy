import { useAuthenticator } from '@aws-amplify/ui-react'
import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { LoginScreen } from './auth/LoginScreen'
import { RequireAuth } from './auth/RequireAuth'
import { AppFrame } from './components/AppFrame'
import { HomePage } from './pages/HomePage'
import { LandingPage } from './pages/LandingPage'
import { RecipeIngredientsPage } from './pages/RecipeIngredientsPage'
import { RecipeIntroPage } from './pages/RecipeIntroPage'
import { RecipeStepsPage } from './pages/RecipeStepsPage'

/** A page that needs a signed-in user, inside the app's chrome. */
function Protected({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <AppFrame>{children}</AppFrame>
    </RequireAuth>
  )
}

/**
 * Every route in one table, deliberately flat.
 *
 * An earlier version nested a second <Routes> inside a `/recipes/*` route. Nested routes
 * match against the *remaining* path, so an inner `/recipes/:id` never matched — clicking a
 * result rendered a blank page with no request and no error.
 */
export default function App() {
  const { authStatus } = useAuthenticator((context) => [context.authStatus])

  return (
    <Routes>
      {/* `/` is the front door: the landing page for visitors, the pantry for members. */}
      <Route
        path="/"
        element={
          authStatus === 'authenticated' ? (
            <Protected>
              <HomePage />
            </Protected>
          ) : (
            <LandingPage />
          )
        }
      />

      <Route
        path="/login"
        element={authStatus === 'authenticated' ? <Navigate to="/" replace /> : <LoginScreen />}
      />

      {/* One page per URL, so back, forward and refresh all behave (spec US-7). */}
      <Route
        path="/recipes/:id"
        element={
          <Protected>
            <RecipeIntroPage />
          </Protected>
        }
      />
      <Route
        path="/recipes/:id/ingredients"
        element={
          <Protected>
            <RecipeIngredientsPage />
          </Protected>
        }
      />
      <Route
        path="/recipes/:id/steps"
        element={
          <Protected>
            <RecipeStepsPage />
          </Protected>
        }
      />
    </Routes>
  )
}
