/** Ingredient search box with autocomplete (spec 10.1). */

import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
} from '@headlessui/react'
import { useMemo, useState } from 'react'

import type { Ingredient } from '../api/types'
import { filterIngredients } from '../lib/ingredientFilter'

interface Props {
  ingredients: Ingredient[]
  ownedIds: ReadonlySet<number>
  onAdd: (ingredient: Ingredient) => void
  disabled?: boolean
}

export function IngredientCombobox({ ingredients, ownedIds, onAdd, disabled }: Props) {
  const [query, setQuery] = useState('')

  const { suggestions, didYouMean } = useMemo(
    () => filterIngredients(ingredients, query, ownedIds),
    [ingredients, query, ownedIds],
  )

  // "Did you mean…?" options are never selected by pressing Enter: the user must choose one.
  const options = suggestions
  const showDidYouMean = suggestions.length === 0 && didYouMean.length > 0
  const showNoMatch = query.trim() !== '' && suggestions.length === 0 && didYouMean.length === 0

  function handleSelect(ingredient: Ingredient | null) {
    if (!ingredient) return
    onAdd(ingredient)
    setQuery('')
  }

  return (
    <div className="relative">
      <Combobox value={null} onChange={handleSelect} disabled={disabled}>
        <div className="flex items-center gap-2 rounded-full border border-forest/20 bg-white px-5 py-3 shadow-sm focus-within:border-forest">
          <ComboboxInput
            aria-label="Add an ingredient"
            placeholder="Add an ingredient…"
            className="w-full bg-transparent text-base text-ink outline-none placeholder:text-muted/70"
            displayValue={() => query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <ComboboxButton className="text-muted" aria-label="Show suggestions">
            ⌄
          </ComboboxButton>
        </div>

        {options.length > 0 && (
          <ComboboxOptions className="absolute z-10 mt-2 w-full overflow-hidden rounded-3xl border border-forest/15 bg-white shadow-lg">
            {options.map((ingredient) => (
              <ComboboxOption
                key={ingredient.id}
                value={ingredient}
                className="cursor-pointer px-5 py-2.5 text-ink data-focus:bg-forest-light"
              >
                {ingredient.display_name}
              </ComboboxOption>
            ))}
          </ComboboxOptions>
        )}
      </Combobox>

      {showDidYouMean && (
        <div className="absolute z-10 mt-2 w-full rounded-3xl border border-dashed border-forest/40 bg-white p-4 shadow-lg">
          <p className="mb-2 text-sm font-medium text-muted">Did you mean…?</p>
          <div className="flex flex-wrap gap-2">
            {didYouMean.map((ingredient) => (
              <button
                key={ingredient.id}
                type="button"
                onClick={() => {
                  onAdd(ingredient)
                  setQuery('')
                }}
                className="rounded-full bg-forest-light px-4 py-1.5 text-sm font-medium text-forest-dark hover:bg-forest hover:text-white"
              >
                {ingredient.display_name}
              </button>
            ))}
          </div>
        </div>
      )}

      {showNoMatch && (
        <p className="absolute z-10 mt-2 w-full rounded-3xl border border-forest/15 bg-white px-5 py-3 text-sm text-muted shadow-lg">
          No match — try a simpler name
        </p>
      )}
    </div>
  )
}
