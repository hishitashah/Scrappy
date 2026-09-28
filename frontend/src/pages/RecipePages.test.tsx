import { screen, waitForElementToBeRemoved, within } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'

import { recipe, resetRecipe } from '../test/handlers'
import { renderWithQuery } from '../test/render'
import { RecipeIngredientsPage } from './RecipeIngredientsPage'
import { RecipeIntroPage } from './RecipeIntroPage'
import { RecipeStepsPage } from './RecipeStepsPage'

/** Render one recipe page at its real URL, so `useParams` sees the id. */
async function renderAt(path: string, element: ReactElement, routePath: string) {
  renderWithQuery(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>,
  )
  await waitForElementToBeRemoved(() => screen.queryByTestId('recipe-skeleton'))
}

const intro = () => renderAt('/recipes/42', <RecipeIntroPage />, '/recipes/:id')
const ingredients = () =>
  renderAt('/recipes/42/ingredients', <RecipeIngredientsPage />, '/recipes/:id/ingredients')
const steps = () => renderAt('/recipes/42/steps', <RecipeStepsPage />, '/recipes/:id/steps')

describe('recipe intro page', () => {
  it('shows the title, tags and photo', async () => {
    await intro()

    expect(screen.getAllByText('Egg fried rice').length).toBeGreaterThan(0)
    expect(screen.getByText('Rice')).toBeInTheDocument()
    expect(screen.getByText('Chinese')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Egg fried rice' })).toHaveAttribute(
      'src',
      'https://example.test/egg-fried-rice.jpg',
    )
  })

  it('advances to the ingredients page, with a label not just an arrow', async () => {
    await intro()

    expect(screen.getByRole('link', { name: 'Ingredients' })).toHaveAttribute(
      'href',
      '/recipes/42/ingredients',
    )
  })

  it('omits the photo when the recipe has none', async () => {
    resetRecipe(recipe({ image_url: null }))

    await intro()

    expect(screen.queryByRole('img', { name: 'Egg fried rice' })).not.toBeInTheDocument()
  })
})

describe('recipe ingredients page', () => {
  it('lists every ingredient with its measure, in recipe order', async () => {
    await ingredients()

    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(6)
    expect(items[0]).toHaveTextContent('Rice — 2 cups')
    expect(items[1]).toHaveTextContent('Egg — 3')
    expect(items[5]).toHaveTextContent('Salt')
  })

  it('counts what the user has', async () => {
    await ingredients()

    expect(screen.getByText('You have 4 of 6')).toBeInTheDocument()
  })

  it('marks missing ingredients distinctly from owned ones', async () => {
    await ingredients()

    const items = screen.getAllByRole('listitem')
    // Owned rows carry no "missing" tag; the two the user lacks do.
    expect(within(items[0]!).queryByText('missing')).not.toBeInTheDocument()
    expect(within(items[4]!).getByText('missing')).toBeInTheDocument()
    expect(within(items[5]!).getByText('missing')).toBeInTheDocument()
  })

  it('moves forward to the steps and back to the overview', async () => {
    await ingredients()

    expect(screen.getByRole('link', { name: 'Instructions' })).toHaveAttribute(
      'href',
      '/recipes/42/steps',
    )
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/recipes/42')
  })
})

describe('recipe steps page', () => {
  it('shows the numbered steps in order', async () => {
    await steps()

    const items = screen.getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      'Boil the rice.',
      'Fry the eggs.',
      'Combine and serve.',
    ])
  })

  it('links to the video and the original recipe', async () => {
    await steps()

    expect(screen.getByRole('link', { name: /Watch video/ })).toHaveAttribute(
      'href',
      'https://example.test/video',
    )
    expect(screen.getByRole('link', { name: /Original recipe/ })).toHaveAttribute(
      'href',
      'https://example.test/source',
    )
  })

  it('omits the links when the recipe has neither', async () => {
    resetRecipe(recipe({ youtube_url: null, source_url: null }))

    await steps()

    expect(screen.queryByRole('link', { name: /Watch video/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Original recipe/ })).not.toBeInTheDocument()
  })

  it('goes back to the ingredients and ends the flow at the results', async () => {
    await steps()

    expect(screen.getByRole('link', { name: 'Ingredients' })).toHaveAttribute(
      'href',
      '/recipes/42/ingredients',
    )
    expect(screen.getByRole('link', { name: 'Back to results' })).toHaveAttribute('href', '/')
  })
})

describe('a recipe that does not exist', () => {
  it.each([
    ['intro', intro],
    ['ingredients', ingredients],
    ['steps', steps],
  ])('shows "Recipe not found" on the %s page', async (_name, render) => {
    resetRecipe(null)

    await render()

    expect(screen.getByText('Recipe not found')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to results' })).toHaveAttribute('href', '/')
  })
})
