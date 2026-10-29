import { screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { resetPantry } from './test/handlers'
import { renderWithQuery } from './test/render'

// Auth state is Amplify's; what matters here is which route renders for a signed-in user.
const { mockAuthStatus } = vi.hoisted(() => ({ mockAuthStatus: { value: 'authenticated' } }))

vi.mock('@aws-amplify/ui-react', () => ({
  useAuthenticator: () => ({ authStatus: mockAuthStatus.value }),
  Authenticator: Object.assign(() => <div>sign in</div>, {
    Provider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }),
}))

vi.mock('./auth/session', () => ({
  accessToken: () => Promise.resolve('test-token'),
  signOut: () => Promise.resolve(),
}))

function renderAt(path: string) {
  renderWithQuery(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('routing', () => {
  beforeEach(() => {
    mockAuthStatus.value = 'authenticated'
    resetPantry()
  })

  // The regression this file exists for: a nested <Routes> made /recipes/:id match nothing,
  // so clicking a result rendered a blank page — no request, no error, no failing test.
  it.each([
    ['/recipes/42', 'Egg fried rice'],
    ['/recipes/42/ingredients', 'Ingredients'],
    ['/recipes/42/steps', 'Step by step instructions'],
  ])('renders %s for a signed-in user', async (path, expected) => {
    renderAt(path)

    expect(await screen.findAllByText(new RegExp(expected, 'i'))).not.toHaveLength(0)
  })

  it('shows the pantry at / for a signed-in user', async () => {
    renderAt('/')

    expect(await screen.findByText('Your pantry')).toBeInTheDocument()
  })

  it('shows the landing page at / for a visitor', async () => {
    mockAuthStatus.value = 'unauthenticated'

    renderAt('/')

    expect(await screen.findByRole('heading', { name: 'SCRAPPY' })).toBeInTheDocument()
  })

  it('keeps a visitor out of a recipe page', async () => {
    mockAuthStatus.value = 'unauthenticated'

    renderAt('/recipes/42')

    // Redirected to the landing page rather than shown the recipe.
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'SCRAPPY' })).toBeInTheDocument(),
    )
  })
})
