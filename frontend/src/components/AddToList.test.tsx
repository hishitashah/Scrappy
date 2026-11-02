import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { groceryItem, recipe, resetGroceryList } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { AddAllMissingButton, AddToListButton } from './AddToList'

const ADD = 'Add to list'

/** Count the add requests, and remember what each one carried. */
function trackAdds() {
  const bodies: number[][] = []
  server.events.on('request:start', async ({ request }) => {
    if (request.method === 'POST' && request.url.endsWith('/grocery-list/items')) {
      const body = (await request.clone().json()) as { ingredient_ids: number[] }
      bodies.push(body.ingredient_ids)
    }
  })
  return () => bodies
}

// The fixture recipe is missing Olive Oil (4) and Salt (5); the rest are owned.
const missing = () => recipe().ingredients.filter((ingredient) => !ingredient.owned)

describe('AddToListButton', () => {
  it('offers to add an ingredient the cook is missing', async () => {
    renderWithQuery(<AddToListButton ingredient={missing()[0]!} />)

    expect(await screen.findByRole('button', { name: ADD })).toBeInTheDocument()
  })

  it('reads "On your list" for one already there, with nothing to press', async () => {
    // Olive Oil is id 4 in the fixture catalog.
    resetGroceryList([groceryItem(4)])

    renderWithQuery(<AddToListButton ingredient={missing()[0]!} />)

    expect(await screen.findByText('On your list')).toBeInTheDocument()
    // A second press could do nothing useful, so it isn't offered.
    expect(screen.queryByRole('button', { name: ADD })).not.toBeInTheDocument()
  })

  it('switches to "On your list" once pressed', async () => {
    const user = userEvent.setup()
    renderWithQuery(<AddToListButton ingredient={missing()[0]!} />)

    await user.click(await screen.findByRole('button', { name: ADD }))

    // From the server's list, not local state — which is what makes it survive a reload.
    expect(await screen.findByText('On your list')).toBeInTheDocument()
  })
})

describe('AddAllMissingButton', () => {
  it('names how many are left to add', async () => {
    renderWithQuery(<AddAllMissingButton ingredients={recipe().ingredients} />)

    expect(await screen.findByRole('button', { name: 'Add all 2 to list' })).toBeInTheDocument()
  })

  it('counts only what is missing and not already listed', async () => {
    resetGroceryList([groceryItem(4)])

    renderWithQuery(<AddAllMissingButton ingredients={recipe().ingredients} />)

    expect(await screen.findByRole('button', { name: 'Add all 1 to list' })).toBeInTheDocument()
  })

  it('adds every missing ingredient in one request', async () => {
    const adds = trackAdds()
    const user = userEvent.setup()
    renderWithQuery(<AddAllMissingButton ingredients={recipe().ingredients} />)

    await user.click(await screen.findByRole('button', { name: 'Add all 2 to list' }))

    // One call, not one per ingredient: the endpoint takes up to 50 ids (spec 10.13).
    await waitFor(() => expect(adds()).toHaveLength(1))
    expect(adds()[0]).toEqual([4, 5])
  })

  it('disappears once everything missing is listed', async () => {
    resetGroceryList([groceryItem(4), groceryItem(5)])

    renderWithQuery(<AddAllMissingButton ingredients={recipe().ingredients} />)

    // Nothing left to do, so no button that would do nothing.
    await waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument())
  })

  it('is absent for a recipe the cook can already make', async () => {
    const complete = recipe().ingredients.map((ingredient) => ({ ...ingredient, owned: true }))

    renderWithQuery(<AddAllMissingButton ingredients={complete} />)

    await waitFor(() => expect(screen.queryByRole('button')).not.toBeInTheDocument())
  })
})

/* Which rows get a button, and that the "missing" pill survives beside it, are asserted
   against the real page in `pages/RecipePages.test.tsx`. */
