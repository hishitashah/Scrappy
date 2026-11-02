import { screen, waitFor, waitForElementToBeRemoved, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { useAddPantryItems } from '../api/hooks'
import { groceryItem, resetGroceryList, resetMe } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { GroceryListPage } from './GroceryListPage'

const API = 'http://localhost:8000'

async function renderList() {
  renderWithQuery(
    <MemoryRouter>
      <GroceryListPage />
    </MemoryRouter>,
  )
  await waitForElementToBeRemoved(() => screen.queryByTestId('grocery-skeleton'))
}

/** Olive Oil (4) and Salt (5) from the fixture catalog. */
function twoItems() {
  resetGroceryList([groceryItem(4), groceryItem(5)])
}

describe('GroceryListPage', () => {
  it('says the list is empty, and still offers the picker', async () => {
    await renderList()

    expect(screen.getByText(/Nothing to buy yet/i)).toBeInTheDocument()
    // Choosing where to shop is useful before there is anything to shop for.
    expect(screen.getByRole('button', { name: 'Choose a store' })).toBeInTheDocument()
  })

  it('shows every saved item', async () => {
    twoItems()

    await renderList()

    expect(screen.getByText('Olive Oil')).toBeInTheDocument()
    expect(screen.getByText('Salt')).toBeInTheDocument()
  })

  it('asks for a store before offering a link, rather than linking nowhere', async () => {
    twoItems()

    await renderList()

    expect(screen.getAllByText('Pick a store')).toHaveLength(3) // two rows plus the picker
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('links each item to the chosen store, with the name encoded', async () => {
    twoItems()
    resetMe('walmart')

    await renderList()

    // Every row gets its own link, so scope to the one being asserted.
    const rows = screen.getAllByRole('listitem')
    const link = within(rows[0]!).getByRole('link', { name: /Find at Walmart/ })
    // The space has to be encoded or the retailer searches for "Olive" alone.
    expect(link).toHaveAttribute('href', 'https://www.walmart.com/search?q=Olive%20Oil')
    // noreferrer, so the retailer isn't told which page sent the shopper (spec 10.13).
    expect(link).toHaveAttribute('rel', 'noreferrer')
    expect(link).toHaveAttribute('target', '_blank')

    expect(within(rows[1]!).getByRole('link', { name: /Find at Walmart/ })).toHaveAttribute(
      'href',
      'https://www.walmart.com/search?q=Salt',
    )
  })

  it('updates the links when a store is chosen', async () => {
    twoItems()
    const user = userEvent.setup()
    await renderList()

    await user.click(screen.getByRole('button', { name: 'Choose a store' }))
    await user.click(await screen.findByRole('option', { name: 'Target' }))

    await waitFor(() => expect(screen.getAllByRole('link')).toHaveLength(2))
    const rows = screen.getAllByRole('listitem')
    expect(within(rows[0]!).getByRole('link', { name: /Find at Target/ })).toHaveAttribute(
      'href',
      'https://www.target.com/s?searchTerm=Olive%20Oil',
    )
  })

  it('removes an item at once', async () => {
    twoItems()
    const user = userEvent.setup()
    await renderList()

    await user.click(screen.getByRole('button', { name: 'Remove Olive Oil' }))

    // Optimistic, so it is already gone — no waiting on the round trip.
    expect(screen.queryByText('Olive Oil')).not.toBeInTheDocument()
    expect(screen.getByText('Salt')).toBeInTheDocument()
    // And it stays gone once the server has answered.
    await waitFor(() => expect(screen.queryByText('Olive Oil')).not.toBeInTheDocument())
  })

  it('puts a removed item back when the server rejects it', async () => {
    twoItems()
    server.use(
      http.delete(`${API}/grocery-list/items/:id`, () => new HttpResponse(null, { status: 500 })),
    )
    const user = userEvent.setup()
    await renderList()

    await user.click(screen.getByRole('button', { name: 'Remove Olive Oil' }))

    // The optimistic removal is rolled back, and the failure is announced.
    expect(await screen.findByRole('alert')).toHaveTextContent(/Couldn't remove/i)
    expect(await screen.findByText('Olive Oil')).toBeInTheDocument()
  })

  it('needs two presses to clear the list', async () => {
    twoItems()
    const user = userEvent.setup()
    await renderList()

    await user.click(screen.getByRole('button', { name: 'Clear list' }))

    // Armed, not cleared: the list is still there.
    expect(screen.getByRole('button', { name: 'Clear the whole list?' })).toBeInTheDocument()
    expect(screen.getByText('Olive Oil')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear the whole list?' }))

    expect(await screen.findByText(/Nothing to buy yet/i)).toBeInTheDocument()
  })

  it('forgets an abandoned first press', async () => {
    twoItems()
    const user = userEvent.setup()
    await renderList()

    await user.click(screen.getByRole('button', { name: 'Clear list' }))
    // Clicking elsewhere blurs the button, which disarms it — so a stray click followed by
    // a later, unrelated click can never empty the list.
    await user.click(screen.getByText('Olive Oil'))

    expect(await screen.findByRole('button', { name: 'Clear list' })).toBeInTheDocument()
    expect(screen.getByText('Olive Oil')).toBeInTheDocument()
  })

  it('drops an item once it has been bought', async () => {
    // The cross-table rule (spec 10.13): `POST /pantry/items` deletes those rows
    // server-side, so the list has to be invalidated or it keeps showing something the
    // user already owns. The server-side half is tested in test_grocery_api.py; this is
    // the half that lives in `useAddPantryItems.onSettled`.
    twoItems()
    const user = userEvent.setup()

    function Harness() {
      const addToPantry = useAddPantryItems()
      return (
        <>
          <button type="button" onClick={() => addToPantry.mutate([4])}>
            Buy Olive Oil
          </button>
          <GroceryListPage />
        </>
      )
    }

    renderWithQuery(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    )
    await waitForElementToBeRemoved(() => screen.queryByTestId('grocery-skeleton'))
    expect(screen.getByText('Olive Oil')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Buy Olive Oil' }))

    await waitFor(() => expect(screen.queryByText('Olive Oil')).not.toBeInTheDocument())
    // Only the bought one goes; the rest of the shopping stands.
    expect(screen.getByText('Salt')).toBeInTheDocument()
  })

  it('offers "Try again" when the list fails to load', async () => {
    server.use(http.get(`${API}/grocery-list`, () => new HttpResponse(null, { status: 500 })))

    renderWithQuery(
      <MemoryRouter>
        <GroceryListPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/Couldn't load your list/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('names each remove button after its ingredient', async () => {
    twoItems()

    await renderList()

    // One × per row would be ambiguous to a screen reader without the ingredient's name.
    const rows = screen.getAllByRole('listitem')
    expect(within(rows[0]!).getByRole('button', { name: 'Remove Olive Oil' })).toBeInTheDocument()
    expect(within(rows[1]!).getByRole('button', { name: 'Remove Salt' })).toBeInTheDocument()
  })
})
