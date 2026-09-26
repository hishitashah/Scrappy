import { screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import { pantryItem, resetPantry } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { server } from '../test/server'
import { PantryEditor } from './PantryEditor'

const API = 'http://localhost:8000'

async function renderPantry() {
  const user = userEvent.setup()
  renderWithQuery(<PantryEditor />)
  await waitForElementToBeRemoved(() => screen.queryByTestId('pantry-skeleton'))
  return user
}

describe('PantryEditor', () => {
  beforeEach(() => resetPantry())

  it('suggests Egg when the user types "egg"', async () => {
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'egg')

    expect(await screen.findByRole('option', { name: 'Egg' })).toBeInTheDocument()
  })

  it('still suggests Egg for "1 egg" and Rice for "a cup of rice"', async () => {
    const user = await renderPantry()
    const input = screen.getByLabelText('Add an ingredient')

    await user.type(input, '1 egg')
    expect(await screen.findByRole('option', { name: 'Egg' })).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, 'a cup of rice')
    expect(await screen.findByRole('option', { name: 'Rice' })).toBeInTheDocument()
  })

  it('adds an ingredient as a chip when a suggestion is chosen', async () => {
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'egg')
    await user.click(await screen.findByRole('option', { name: 'Egg' }))

    expect(await screen.findByRole('button', { name: 'Remove Egg' })).toBeInTheDocument()
  })

  it('does not suggest an ingredient already in the pantry', async () => {
    resetPantry([pantryItem(1)])
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'egg')

    await waitFor(() => expect(screen.queryByRole('option', { name: 'Egg' })).not.toBeInTheDocument())
  })

  it('offers "Did you mean…?" for a misspelling, and Enter alone adds nothing', async () => {
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'garlick')

    expect(await screen.findByText('Did you mean…?')).toBeInTheDocument()
    const suggestion = screen.getByRole('button', { name: 'Garlic' })

    await user.keyboard('{Enter}')
    expect(screen.queryByRole('button', { name: 'Remove Garlic' })).not.toBeInTheDocument()

    await user.click(suggestion)
    expect(await screen.findByRole('button', { name: 'Remove Garlic' })).toBeInTheDocument()
  })

  it('shows "No match" for text close to nothing', async () => {
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'zzzzz')

    expect(await screen.findByText('No match — try a simpler name')).toBeInTheDocument()
    expect(screen.queryByText('Did you mean…?')).not.toBeInTheDocument()
  })

  it('removes a chip before the server responds', async () => {
    resetPantry([pantryItem(1)])
    let released: (() => void) | undefined
    const blocked = new Promise<void>((resolve) => {
      released = resolve
    })
    server.use(
      http.delete(`${API}/pantry/items/:id`, async () => {
        await blocked
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = await renderPantry()

    await user.click(screen.getByRole('button', { name: 'Remove Egg' }))

    // Gone immediately, while the request is still in flight.
    expect(screen.queryByRole('button', { name: 'Remove Egg' })).not.toBeInTheDocument()
    released?.()
  })

  it('restores the chip when the delete fails', async () => {
    resetPantry([pantryItem(1)])
    server.use(
      http.delete(`${API}/pantry/items/:id`, () => new HttpResponse(null, { status: 500 })),
    )
    const user = await renderPantry()

    await user.click(screen.getByRole('button', { name: 'Remove Egg' }))

    expect(await screen.findByRole('button', { name: 'Remove Egg' })).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't remove that ingredient")
  })

  it('says water is assumed and asks for the other basics', async () => {
    await renderPantry()

    expect(
      screen.getByText('Tip: water is assumed. Add basics like salt and oil for more accurate matches.'),
    ).toBeInTheDocument()
  })

  it('never suggests an assumed staple', async () => {
    const user = await renderPantry()

    await user.type(screen.getByLabelText('Add an ingredient'), 'water')

    await waitFor(() =>
      expect(screen.queryByRole('option', { name: 'Water' })).not.toBeInTheDocument(),
    )
  })
})
