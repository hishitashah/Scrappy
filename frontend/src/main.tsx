import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import App from './App'
import { Authenticator } from '@aws-amplify/ui-react'

import { configureAuth } from './auth/amplify'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

// Before anything renders: Amplify needs its configuration in place first.
configureAuth()

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {/* Provides auth state to the whole tree; the login wall itself is now a route. */}
        <Authenticator.Provider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </Authenticator.Provider>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
