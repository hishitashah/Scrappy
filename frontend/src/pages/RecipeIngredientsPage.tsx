/** `/recipes/:id/ingredients` — every ingredient, owned ones marked (spec 10.3). */

import { useParams } from 'react-router'

import { useRecipe } from '../api/hooks'
import type { RecipeIngredient } from '../api/types'
import { RecipePageFrame } from '../components/RecipePageFrame'

export function RecipeIngredientsPage() {
  const { id } = useParams()
  const recipeId = Number(id)
  const query = useRecipe(recipeId)

  return (
    <RecipePageFrame
      heading="Ingredients"
      query={query}
      previous={{ to: `/recipes/${recipeId}`, label: 'Overview' }}
      next={{ to: `/recipes/${recipeId}/steps`, label: 'Instructions' }}
    >
      {(recipe) => {
        // Counting the `owned` flags the API already returned. Matching itself stays in
        // the SQL query (spec 10.2); nothing is ranked or recomputed here.
        const owned = recipe.ingredients.filter((ingredient) => ingredient.owned).length

        return (
          <>
            <p className="mb-5 text-sm font-medium text-cream/80">
              You have {owned} of {recipe.ingredients.length}
            </p>
            <ul className="flex flex-col gap-3">
              {recipe.ingredients.map((ingredient) => (
                <IngredientRow key={ingredient.id} ingredient={ingredient} />
              ))}
            </ul>
          </>
        )
      }}
    </RecipePageFrame>
  )
}

function IngredientRow({ ingredient }: { ingredient: RecipeIngredient }) {
  // Owned and missing differ by mark, weight and opacity — never by color alone.
  return (
    <li className={`flex items-baseline gap-3 ${ingredient.owned ? '' : 'text-cream/55'}`}>
      <span aria-hidden="true" className="w-4 shrink-0 text-center">
        {ingredient.owned ? '✓' : '•'}
      </span>
      <span className={ingredient.owned ? 'font-medium' : ''}>
        {ingredient.display_name}
        {ingredient.measure && <span className="text-cream/70"> — {ingredient.measure}</span>}
      </span>
      {!ingredient.owned && (
        <span className="ml-auto shrink-0 rounded-full bg-cream/10 px-2 py-0.5 text-xs">
          missing
        </span>
      )}
    </li>
  )
}
