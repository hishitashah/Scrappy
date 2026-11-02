import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { generatedRecipe } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { GenerateRecipeButton } from './GenerateRecipeButton'

const API = 'http://localhost:8000'
const BUTTON = 'Generate a recipe from my ingredients'

/** Count what reaches the API, so "nothing is requested" can be asserted directly. */
function countRequests() {
  let calls = 0
  server.events.on('request:start', ({ request }) => {
    if (request.method === 'POST' && request.url.endsWith('/recipes/generate')) calls += 1
  })
  return () => calls
}

function failWith(status: number) {
  server.use(
    http.post(`${API}/recipes/generate`, () => HttpResponse.json({ detail: 'nope' }, { status })),
  )
}

/**
 * The button where it really lives, with a stub at the recipe route — so "it navigates"
 * is asserted through the router rather than by spying on `useNavigate`.
 */
function renderButton() {
  renderWithQuery(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<GenerateRecipeButton />} />
        <Route path="/recipes/:id" element={<div>recipe page for 51</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('GenerateRecipeButton', () => {
  it('asks for nothing until the button is pressed', async () => {
    // The guardrail that matters most: every press spends money, so rendering the empty
    // state must cost nothing (spec 14). The press at the end is what proves the counter
    // is actually watching — one that never moves would pass the first assertion for the
    // wrong reason.
    const calls = countRequests()
    const user = userEvent.setup()

    renderButton()

    expect(screen.getByRole('button', { name: BUTTON })).toBeInTheDocument()
    await waitFor(() => expect(calls()).toBe(0))

    await user.click(screen.getByRole('button', { name: BUTTON }))

    await waitFor(() => expect(calls()).toBe(1))
  })

  it('opens the new recipe once it has been written', async () => {
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText('recipe page for 51')).toBeInTheDocument()
  })

  it('says it is working, because writing a recipe takes a while', async () => {
    server.use(
      http.post(`${API}/recipes/generate`, async () => {
        // Long enough to observe the pending label, short enough not to slow the suite.
        await new Promise((resolve) => setTimeout(resolve, 50))
        return HttpResponse.json(generatedRecipe())
      }),
    )
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByRole('button', { name: 'Writing a recipe…' })).toBeDisabled()
    expect(await screen.findByText('recipe page for 51')).toBeInTheDocument()
  })

  it('explains the daily limit', async () => {
    failWith(429)
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/today's recipes/i)).toBeInTheDocument()
    // Pressing again would spend nothing and change nothing, so no retry is offered.
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('explains a paused feature', async () => {
    failWith(503)
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/paused until next month/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('offers a retry for anything else, and the retry works', async () => {
    failWith(502)
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))
    expect(await screen.findByText(/couldn't write a recipe/i)).toBeInTheDocument()

    // The model was unreachable, not wrong, so asking again is reasonable.
    server.use(http.post(`${API}/recipes/generate`, () => HttpResponse.json(generatedRecipe())))
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('recipe page for 51')).toBeInTheDocument()
  })

  it('does not report an empty pantry as a model failure', async () => {
    // The endpoint refuses an empty pantry with 422. The button shouldn't be reachable in
    // that state at all (ResultsList hides it), but if it is, the message must not blame
    // the model for something the user can fix.
    failWith(422)
    const user = userEvent.setup()
    renderButton()

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/couldn't write a recipe/i)).toBeInTheDocument()
    expect(screen.queryByText(/paused/i)).not.toBeInTheDocument()
  })
})
