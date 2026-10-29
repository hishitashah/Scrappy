/**
 * Browser-side ingredient search (spec 10.1).
 *
 * The whole catalog is a few kilobytes, so filtering happens here rather than costing an
 * API call per keystroke. Quantity and unit words are stripped before matching, because
 * "1 egg" and "a cup of rice" should still find Egg and Rice — nothing about the quantity
 * is kept or stored.
 */

import type { Ingredient } from '../api/types'

export const MAX_SUGGESTIONS = 8
export const MAX_DID_YOU_MEAN = 3

/**
 * Ingredients the app assumes everyone has (spec section 4), mirroring
 * `backend/app/staples.py`. They are never suggested, because they always count already.
 */
export const ASSUMED_STAPLES = new Set(['water'])

const STOPWORDS = new Set([
  'a', 'an', 'the', 'of', 'some',
  'cup', 'cups', 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon', 'teaspoons',
  'oz', 'ounce', 'ounces', 'lb', 'lbs', 'pound', 'pounds',
  'g', 'gram', 'grams', 'kg', 'ml', 'l', 'litre', 'litres', 'liter', 'liters',
  'pinch', 'dash', 'handful', 'clove', 'cloves', 'can', 'cans', 'tin', 'tins',
  'large', 'small', 'medium', 'fresh', 'chopped', 'sliced', 'diced', 'minced',
])

/** "2 Large Eggs" -> "eggs": drop quantities, units and filler words. */
export function stripQuantityWords(query: string): string {
  const words = query.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean)
  const kept: string[] = []
  for (const word of words) {
    // Only skip leading noise: "cup" inside "cup cake" should survive once real words start.
    if (kept.length === 0 && (STOPWORDS.has(word) || /^[\d/.]+$/.test(word))) continue
    kept.push(word)
  }
  return (kept.length > 0 ? kept : words).join(' ')
}

function haystack(ingredient: Ingredient): string[] {
  return [
    ingredient.name.toLowerCase(),
    // The display name carries the plural the catalog's canonical name drops: typing
    // "eggs" has to find the ingredient stored as "egg" and shown as "Eggs".
    ingredient.display_name.toLowerCase(),
    ...ingredient.aliases.map((a) => a.toLowerCase()),
  ]
}

/**
 * English plural endings, enough to meet the catalog's singular names halfway.
 *
 * The import singularizes with a full library; the browser only needs the common cases,
 * and the result is compared against both forms, so a wrong guess costs nothing.
 */
function singular(word: string): string {
  if (word.endsWith('ies') && word.length > 4) return `${word.slice(0, -3)}y`
  if (word.endsWith('ses') || word.endsWith('xes') || word.endsWith('ches')) {
    return word.slice(0, -2)
  }
  if (word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1)
  return word
}

/** The forms of a query worth testing: as typed, and with the last word singularized. */
function queryForms(query: string): string[] {
  const words = query.split(' ')
  const lastWord = words[words.length - 1] ?? ''
  const singularized = [...words.slice(0, -1), singular(lastWord)].join(' ')
  return singularized === query ? [query] : [query, singularized]
}

/** Levenshtein distance, used only for the "Did you mean…?" fallback. */
export function editDistance(a: string, b: string): number {
  if (a === b) return 0
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const current = [i]
    for (let j = 1; j <= b.length; j++) {
      const substitution = (previous[j - 1] ?? 0) + (a[i - 1] === b[j - 1] ? 0 : 1)
      const insertion = (current[j - 1] ?? 0) + 1
      const deletion = (previous[j] ?? 0) + 1
      current[j] = Math.min(substitution, insertion, deletion)
    }
    previous = current
  }
  return previous[b.length] ?? Math.max(a.length, b.length)
}

export interface SuggestionResult {
  /** Ordinary matches: prefix matches first, then anything containing the query. */
  suggestions: Ingredient[]
  /** Close-but-not-exact matches, shown only when `suggestions` is empty. */
  didYouMean: Ingredient[]
}

/**
 * Rank the catalog for a query, excluding what the user already has.
 *
 * Ingredients already in the pantry are never suggested, which makes duplicates
 * impossible (spec 10.1).
 */
export function filterIngredients(
  ingredients: Ingredient[],
  rawQuery: string,
  ownedIds: ReadonlySet<number>,
): SuggestionResult {
  const query = stripQuantityWords(rawQuery)
  if (query === '') return { suggestions: [], didYouMean: [] }

  const available = ingredients.filter(
    (ingredient) => !ownedIds.has(ingredient.id) && !ASSUMED_STAPLES.has(ingredient.name),
  )
  const forms = queryForms(query)
  const exact: Ingredient[] = []
  const prefix: Ingredient[] = []
  const contains: Ingredient[] = []

  for (const ingredient of available) {
    const fields = haystack(ingredient)
    if (fields.some((field) => forms.includes(field))) exact.push(ingredient)
    else if (fields.some((field) => forms.some((form) => field.startsWith(form)))) {
      prefix.push(ingredient)
    } else if (fields.some((field) => forms.some((form) => field.includes(form)))) {
      contains.push(ingredient)
    }
  }

  // Within each tier, the ingredient used by more recipes comes first. Without this,
  // typing "egg" offered "Egg Noodles" before "Eggs" purely because of alphabetical
  // order — and an ingredient in two recipes is nearly useless for matching.
  const byUsefulness = (a: Ingredient, b: Ingredient) =>
    b.recipe_count - a.recipe_count || a.display_name.localeCompare(b.display_name)

  const suggestions = [
    ...exact.sort(byUsefulness),
    ...prefix.sort(byUsefulness),
    ...contains.sort(byUsefulness),
  ].slice(0, MAX_SUGGESTIONS)
  if (suggestions.length > 0) return { suggestions, didYouMean: [] }

  // Nothing matched, so fall back to near-misses: a typo should cost one click, not a retype.
  const tolerance = query.length < 5 ? 1 : 2
  const scored = available
    .map((ingredient) => ({
      ingredient,
      distance: Math.min(...haystack(ingredient).map((field) => editDistance(query, field))),
    }))
    .filter((entry) => entry.distance <= tolerance)
    .sort((a, b) => a.distance - b.distance || a.ingredient.name.localeCompare(b.ingredient.name))

  return {
    suggestions: [],
    didYouMean: scored.slice(0, MAX_DID_YOU_MEAN).map((entry) => entry.ingredient),
  }
}
