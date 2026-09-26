/** The pantry: a search box, the basics hint, and one chip per ingredient (spec 10.1). */

import { useMemo } from 'react'

import { useAddPantryItems, useIngredients, usePantry, useRemovePantryItem } from '../api/hooks'
import type { Ingredient } from '../api/types'
import { IngredientCombobox } from './IngredientCombobox'

export function PantryEditor() {
  const ingredients = useIngredients()
  const pantry = usePantry()
  const addItems = useAddPantryItems()
  const removeItem = useRemovePantryItem()

  const ownedIds = useMemo(
    () => new Set((pantry.data ?? []).map((item) => item.ingredient_id)),
    [pantry.data],
  )

  function handleAdd(ingredient: Ingredient) {
    addItems.mutate([ingredient.id])
  }

  return (
    <section className="rounded-card border border-olive/20 bg-white/60 p-7">
      <h2 className="mb-4 text-2xl font-bold tracking-tight">Your pantry</h2>

      <IngredientCombobox
        ingredients={ingredients.data ?? []}
        ownedIds={ownedIds}
        onAdd={handleAdd}
        disabled={ingredients.isPending}
      />

      <p className="mt-3 text-sm text-muted">
        Tip: water is assumed. Add basics like salt and oil for more accurate matches.
      </p>

      {removeItem.isError && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          Couldn&apos;t remove that ingredient. Please try again.
        </p>
      )}

      <div className="mt-6">
        {pantry.isPending ? (
          <PantrySkeleton />
        ) : pantry.isError ? (
          <div className="text-sm text-muted">
            <p className="mb-2">Couldn&apos;t load your pantry.</p>
            <button
              type="button"
              onClick={() => void pantry.refetch()}
              className="rounded-full bg-forest px-4 py-1.5 font-medium text-white"
            >
              Try again
            </button>
          </div>
        ) : pantry.data.length === 0 ? (
          <p className="text-sm text-muted">Nothing here yet. Add what&apos;s in your kitchen.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {pantry.data.map((item) => (
              <li key={item.ingredient_id}>
                <span className="inline-flex items-center gap-2 rounded-full bg-forest-light px-4 py-1.5 text-sm font-medium text-forest-dark">
                  {item.display_name}
                  <button
                    type="button"
                    aria-label={`Remove ${item.display_name}`}
                    onClick={() => removeItem.mutate(item.ingredient_id)}
                    className="text-forest-dark/60 hover:text-forest-dark"
                  >
                    ×
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function PantrySkeleton() {
  return (
    <div className="flex flex-wrap gap-2" aria-hidden="true" data-testid="pantry-skeleton">
      {[72, 96, 60, 84].map((width) => (
        <div key={width} className="h-8 animate-pulse rounded-full bg-cream-deep" style={{ width }} />
      ))}
    </div>
  )
}
