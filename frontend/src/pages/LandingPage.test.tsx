import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { LandingPage } from './LandingPage'

describe('LandingPage', () => {
  it('leads with what the app does, not a login form', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'SCRAPPY' })).toBeInTheDocument()
    expect(
      screen.getByText(/Most recipe sites send you shopping/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Instant meal generator with what you have available/),
    ).toBeInTheDocument()
    // No password field anywhere: signing in is a destination, not the front door.
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
  })

  it('sends "Get Started" to the login page', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Get Started' })).toHaveAttribute('href', '/login')
  })

  it('describes the photo for screen readers and hides the decoration', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('img', { name: /salad/i })).toBeInTheDocument()
    // The chef hat and the chevron carry no meaning, so they are hidden from assistive tech.
    expect(screen.getAllByRole('img')).toHaveLength(1)
  })
})
