/**
 * Putting a recipe's missing ingredients on the grocery list (F9, spec 10.13).
 *
 * Two buttons, together because they share one question: which of these does the user
 * already have on their list? That comes from `useGroceryList()` rather than from local
 * state, so a row still reads "On your list" after a reload, and goes back to offering
 * the button if the item is removed on `/list`.
 */

import { useAddGroceryItems, useGroceryList } from '../api/hooks'
import type { RecipeIngredient } from '../api/types'

/** Ingredients the cook doesn't have and hasn't already listed. */
function stillToAdd(
  ingredients: RecipeIngredient[],
  listedIds: ReadonlySet<number>,
): RecipeIngredient[] {
  return ingredients.filter((ingredient) => !ingredient.owned && !listedIds.has(ingredient.id))
}

function useListedIds(): ReadonlySet<number> {
  const list = useGroceryList()
  return new Set((list.data ?? []).map((item) => item.ingredient_id))
}

export function AddToListButton({ ingredient }: { ingredient: RecipeIngredient }) {
  const listedIds = useListedIds()
  const addItems = useAddGroceryItems()

  if (listedIds.has(ingredient.id)) {
    // A statement, not a control: there is nothing useful a second press could do.
    return (
      <span className="shrink-0 rounded-full bg-cream/20 px-2.5 py-0.5 text-xs font-semibold">
        On your list
      </span>
    )
  }

  return (
    <button
      type="button"
      onClick={() => addItems.mutate([ingredient.id])}
      className="shrink-0 rounded-full border border-cream/40 px-2.5 py-0.5 text-xs font-medium transition hover:bg-cream/15"
    >
      Add to list
    </button>
  )
}

export function AddAllMissingButton({ ingredients }: { ingredients: RecipeIngredient[] }) {
  const listedIds = useListedIds()
  const addItems = useAddGroceryItems()

  const pending = stillToAdd(ingredients, listedIds)

  // Nothing left to add, so no button. A recipe that is fully listed — or fully owned —
  // shouldn't offer a control that would do nothing.
  if (pending.length === 0) return null

  return (
    <button
      type="button"
      onClick={() => addItems.mutate(pending.map((ingredient) => ingredient.id))}
      disabled={addItems.isPending}
      className="shrink-0 rounded-full bg-cream px-4 py-1.5 text-sm font-medium text-forest-dark transition hover:bg-cream-deep disabled:opacity-70"
    >
      {/* One request for all of them: the endpoint takes up to 50 ids (spec 10.13). */}
      Add all {pending.length} to list
    </button>
  )
}
