import { screen, waitForElementToBeRemoved } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { match, pantryItem, resetMatches, resetPantry } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { ResultsList } from './ResultsList'

const API = 'http://localhost:8000'

async function renderResults() {
  renderWithQuery(
    <MemoryRouter>
      <ResultsList />
    </MemoryRouter>,
  )
  await waitForElementToBeRemoved(() => screen.queryByTestId('results-skeleton'))
}

describe('ResultsList', () => {
  beforeEach(() => {
    resetPantry()
    resetMatches()
  })

  it('shows the have/total count and the missing ingredients', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([match()])

    await renderResults()

    expect(screen.getByText('Egg fried rice')).toBeInTheDocument()
    expect(screen.getByText('You have 3 of 7')).toBeInTheDocument()
    expect(screen.getByText('Missing: Oil, Salt, Soy Sauce, Spring Onion')).toBeInTheDocument()
    expect(screen.getByText('43%')).toBeInTheDocument()
  })

  it('omits the missing line when nothing is missing', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([match({ have: 3, total: 3, match: 100, missing: [] })])

    await renderResults()

    expect(screen.getByText('You have 3 of 3')).toBeInTheDocument()
    expect(screen.queryByText(/^Missing:/)).not.toBeInTheDocument()
  })

  it('links each result to its recipe page', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([match({ id: 42 })])

    await renderResults()

    expect(screen.getByRole('link', { name: /Egg fried rice/ })).toHaveAttribute(
      'href',
      '/recipes/42',
    )
  })

  it('asks for ingredients when the pantry is empty', async () => {
    await renderResults()

    expect(
      screen.getByText('Add a few ingredients to see what you can make.'),
    ).toBeInTheDocument()
  })

  it('asks for more ingredients when nothing clears the 50% floor', async () => {
    resetPantry([pantryItem(1)])

    await renderResults()

    expect(
      screen.getByText("Nothing's close enough yet. Add a few more ingredients."),
    ).toBeInTheDocument()
  })

  it('offers "Try again" when matches fail to load', async () => {
    server.use(http.get(`${API}/matches`, () => new HttpResponse(null, { status: 500 })))

    await renderResults()

    expect(screen.getByText("Couldn't load your matches.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
