import { screen, waitForElementToBeRemoved, within } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { match, pantryItem, resetMatches, resetPantry } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { ResultsList } from './ResultsList'

const API = 'http://localhost:8000'
const GENERATE = 'Generate a recipe from my ingredients'

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

    expect(screen.getByText('Add a few ingredients to see what you can make.')).toBeInTheDocument()
    // Nothing to build a recipe from, and the endpoint would answer 422: a button here
    // would promise something it can't do (spec 10.12).
    expect(screen.queryByRole('button', { name: GENERATE })).not.toBeInTheDocument()
  })

  it('asks for more ingredients when nothing clears the 50% floor', async () => {
    resetPantry([pantryItem(1)])

    await renderResults()

    expect(
      screen.getByText("Nothing's close enough yet. Add a few more ingredients."),
    ).toBeInTheDocument()
    // The dead end F8 exists to answer: a pantry with something in it, matching nothing.
    expect(screen.getByRole('button', { name: GENERATE })).toBeInTheDocument()
  })

  it('labels an AI-written recipe, and only that one', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([
      match({ id: 42, title: 'Egg fried rice' }),
      match({ id: 51, title: 'Garlic Fried Rice', generated: true }),
    ])

    await renderResults()

    const generated = screen.getByRole('link', { name: /Garlic Fried Rice/ })
    const imported = screen.getByRole('link', { name: /Egg fried rice/ })
    expect(within(generated).getByText('AI-generated')).toBeInTheDocument()
    expect(within(imported).queryByText('AI-generated')).not.toBeInTheDocument()
  })

  it('offers "Try again" when matches fail to load', async () => {
    server.use(http.get(`${API}/matches`, () => new HttpResponse(null, { status: 500 })))

    await renderResults()

    expect(screen.getByText("Couldn't load your matches.")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  // --- Meals and sides (spec 10.2) -----------------------------------------------------
  //
  // The 50% floor favours short recipes, and short recipes are sides, so a pantry that
  // could genuinely make dinner can return a page of garnishes. Grouping is what makes
  // that visible instead of leaving the cook to infer it.

  it('separates meals from sides', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([
      match({ id: 1, title: 'Garlic Chicken', is_meal: true }),
      match({ id: 2, title: 'Garlic Bread', is_meal: false }),
    ])

    await renderResults()

    const meals = screen.getByRole('list', { name: 'Meals' })
    const sides = screen.getByRole('list', { name: 'Sides & extras' })
    expect(within(meals).getByText('Garlic Chicken')).toBeInTheDocument()
    expect(within(sides).getByText('Garlic Bread')).toBeInTheDocument()
    // Each in one group only, so neither is double-counted.
    expect(within(meals).queryByText('Garlic Bread')).not.toBeInTheDocument()
    expect(within(sides).queryByText('Garlic Chicken')).not.toBeInTheDocument()
  })

  it('offers to generate a meal when only sides match', async () => {
    // The case that prompted this: chicken, flour, garlic, oil, rice, salt and sugar in
    // the pantry, and nothing but sides on the page. Previously the button was reachable
    // only when *nothing at all* matched, so this cook was never offered it.
    resetPantry([pantryItem(1)])
    resetMatches([match({ title: 'Garlic Bread', is_meal: false })])

    await renderResults()

    expect(screen.getByText(/nothing you can make as a meal yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: GENERATE })).toBeInTheDocument()
    // The sides are still listed — they were never the problem.
    expect(screen.getByText('Garlic Bread')).toBeInTheDocument()
  })

  it('does not offer to generate when a meal already matches', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([
      match({ id: 1, title: 'Garlic Chicken', is_meal: true }),
      match({ id: 2, title: 'Garlic Bread', is_meal: false }),
    ])

    await renderResults()

    expect(screen.queryByRole('button', { name: GENERATE })).not.toBeInTheDocument()
    expect(screen.queryByText(/nothing you can make as a meal yet/i)).not.toBeInTheDocument()
  })

  it('omits the sides group when there are none', async () => {
    resetPantry([pantryItem(1)])
    resetMatches([match({ title: 'Garlic Chicken', is_meal: true })])

    await renderResults()

    expect(screen.getByRole('list', { name: 'Meals' })).toBeInTheDocument()
    // An empty sides group would be noise: it tells the cook nothing they need.
    expect(screen.queryByRole('list', { name: 'Sides & extras' })).not.toBeInTheDocument()
  })

  it('files a generated recipe under meals', async () => {
    // It has no category, and it is the answer offered when no meal matched — so it has
    // to land in the group that was empty, or the page would still be asking for one.
    resetPantry([pantryItem(1)])
    resetMatches([
      match({
        id: 9,
        title: 'Garlic Rice Bowl',
        generated: true,
        is_meal: true,
      }),
      match({ id: 2, title: 'Garlic Bread', is_meal: false }),
    ])

    await renderResults()

    const meals = screen.getByRole('list', { name: 'Meals' })
    expect(within(meals).getByText('Garlic Rice Bowl')).toBeInTheDocument()
    expect(within(meals).getByText('AI-generated')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: GENERATE })).not.toBeInTheDocument()
  })
})
