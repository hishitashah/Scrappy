import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'

import { recipe, substitutions } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { SubstitutionsPanel } from './SubstitutionsPanel'

const API = 'http://localhost:8000'
const BUTTON = 'Suggest substitutions'

/** Count what reaches the API, so "nothing is requested" can be asserted directly. */
function countRequests() {
  let calls = 0
  server.events.on('request:start', ({ request }) => {
    if (request.method === 'POST' && request.url.includes('/substitutions')) calls += 1
  })
  return () => calls
}

function failWith(status: number) {
  server.use(
    http.post(`${API}/recipes/:id/substitutions`, () =>
      HttpResponse.json({ detail: 'nope' }, { status }),
    ),
  )
}

describe('SubstitutionsPanel', () => {
  it('asks for nothing until the button is pressed', async () => {
    // The guardrail that matters most: every call spends money, so rendering the panel
    // must cost nothing (spec 14). The press at the end is what proves the counter is
    // actually watching — a counter that never moves would pass the first assertion for
    // the wrong reason.
    const calls = countRequests()
    const user = userEvent.setup()

    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    expect(screen.getByRole('button', { name: BUTTON })).toBeInTheDocument()
    await waitFor(() => expect(calls()).toBe(0))

    await user.click(screen.getByRole('button', { name: BUTTON }))

    await waitFor(() => expect(calls()).toBe(1))
  })

  it('offers nothing at all when the cook has everything', () => {
    const complete = recipe({
      ingredients: recipe().ingredients.map((ingredient) => ({ ...ingredient, owned: true })),
    })

    renderWithQuery(<SubstitutionsPanel recipe={complete} />)

    // No question to ask, so no button to press — not a disabled one.
    expect(screen.queryByRole('button', { name: BUTTON })).not.toBeInTheDocument()
  })

  it('shows the suggestions, labelled as AI-generated, when pressed', async () => {
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText('Butter')).toBeInTheDocument()
    expect(screen.getByText('Both carry heat and add richness.')).toBeInTheDocument()
    // The label is not decoration: a suggestion must not be able to pass for a recipe step.
    expect(screen.getByRole('heading', { name: /AI-generated suggestions/i })).toBeInTheDocument()
  })

  it('marks a suggestion the cook already has', async () => {
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText('in your pantry')).toBeInTheDocument()
  })

  it('says so when the model had nothing useful to offer', async () => {
    // Fewer suggestions than missing ingredients is a real answer, not a failure.
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () =>
        HttpResponse.json(substitutions({ suggestions: [] })),
      ),
    )
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/needs a shop/i)).toBeInTheDocument()
  })

  it('renders a partial answer without implying a row is missing', async () => {
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () =>
        HttpResponse.json(
          substitutions({ suggestions: [substitutions().suggestions[0]!] }),
        ),
      ),
    )
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText('Butter')).toBeInTheDocument()
    expect(screen.queryByText(/needs a shop/i)).not.toBeInTheDocument()
  })

  it('explains the daily limit', async () => {
    failWith(429)
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/try again tomorrow/i)).toBeInTheDocument()
    // Pressing again would spend nothing and change nothing, so there is no retry offered.
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('explains a paused feature', async () => {
    failWith(503)
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))

    expect(await screen.findByText(/paused until next month/i)).toBeInTheDocument()
  })

  it('offers a retry for anything else, and the retry works', async () => {
    failWith(502)
    const user = userEvent.setup()
    renderWithQuery(<SubstitutionsPanel recipe={recipe()} />)

    await user.click(screen.getByRole('button', { name: BUTTON }))
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()

    // The model was unreachable, not wrong, so asking again is reasonable.
    server.use(
      http.post(`${API}/recipes/:id/substitutions`, () => HttpResponse.json(substitutions())),
    )
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByText('Butter')).toBeInTheDocument()
  })
})
