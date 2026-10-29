import { useAuthenticator } from '@aws-amplify/ui-react'
import { Navigate, Route, Routes } from 'react-router'

import { LoginScreen } from './auth/LoginScreen'
import { RequireAuth } from './auth/RequireAuth'
import { AppFrame } from './components/AppFrame'
import { HomePage } from './pages/HomePage'
import { LandingPage } from './pages/LandingPage'
import { RecipeIngredientsPage } from './pages/RecipeIngredientsPage'
import { RecipeIntroPage } from './pages/RecipeIntroPage'
import { RecipeStepsPage } from './pages/RecipeStepsPage'

/** The app itself, which only ever renders for a signed-in user. */
function AuthenticatedApp() {
  return (
    <AppFrame>
      <Routes>
        <Route path="/" element={<HomePage />} />
        {/* One page per URL, so back, forward and refresh all behave (spec US-7). */}
        <Route path="/recipes/:id" element={<RecipeIntroPage />} />
        <Route path="/recipes/:id/ingredients" element={<RecipeIngredientsPage />} />
        <Route path="/recipes/:id/steps" element={<RecipeStepsPage />} />
      </Routes>
    </AppFrame>
  )
}

export default function App() {
  const { authStatus } = useAuthenticator((context) => [context.authStatus])

  return (
    <Routes>
      {/* `/` is the front door: the landing page for visitors, the pantry for members. */}
      <Route
        path="/"
        element={authStatus === 'authenticated' ? <AuthenticatedApp /> : <LandingPage />}
      />

      <Route
        path="/login"
        element={authStatus === 'authenticated' ? <Navigate to="/" replace /> : <LoginScreen />}
      />

      {/* Everything else is behind the wall, and bounces to the landing page when signed out. */}
      <Route
        path="/recipes/*"
        element={
          <RequireAuth>
            <AuthenticatedApp />
          </RequireAuth>
        }
      />
    </Routes>
  )
}
