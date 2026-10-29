import { describe, expect, it } from 'vitest'

import type { Ingredient } from '../api/types'
import { filterIngredients, stripQuantityWords } from './ingredientFilter'

/** Mirrors the real catalog's shape: a common ingredient alongside rare variants. */
const catalog: Ingredient[] = [
  { id: 1, name: 'egg', display_name: 'Eggs', aliases: ['eggs'], recipe_count: 218 },
  { id: 2, name: 'rice', display_name: 'Rice', aliases: [], recipe_count: 35 },
  { id: 3, name: 'garlic', display_name: 'Garlic', aliases: ['garlic clove'], recipe_count: 300 },
  {
    id: 4,
    name: 'olive oil',
    display_name: 'Olive Oil',
    aliases: ['extra virgin olive oil'],
    recipe_count: 120,
  },
  { id: 5, name: 'tomato', display_name: 'Tomatoes', aliases: [], recipe_count: 90 },
  { id: 6, name: 'egg plant', display_name: 'Egg Plants', aliases: [], recipe_count: 9 },
  {
    id: 7,
    name: 'free range egg beaten',
    display_name: 'Free-range Egg, Beaten',
    aliases: [],
    recipe_count: 2,
  },
  { id: 8, name: 'onion', display_name: 'Onions', aliases: [], recipe_count: 254 },
  { id: 9, name: 'ground onion', display_name: 'Ground Onion', aliases: ['onion powder'], recipe_count: 1 },
]

const names = (result: Ingredient[]) => result.map((i) => i.display_name)

describe('stripQuantityWords', () => {
  it.each([
    ['1 egg', 'egg'],
    ['a cup of rice', 'rice'],
    ['2 large eggs', 'eggs'],
    ['  GARLIC  ', 'garlic'],
    ['3 tbsp olive oil', 'olive oil'],
  ])('%s -> %s', (input, expected) => {
    expect(stripQuantityWords(input)).toBe(expected)
  })

  it('keeps the words when a query is only quantity words', () => {
    expect(stripQuantityWords('cup')).toBe('cup')
  })
})

describe('filterIngredients', () => {
  const none = new Set<number>()

  it('suggests Egg for "egg"', () => {
    expect(names(filterIngredients(catalog, 'egg', none).suggestions)).toContain('Eggs')
  })

  it('still suggests Egg for "1 egg" and Rice for "a cup of rice"', () => {
    expect(names(filterIngredients(catalog, '1 egg', none).suggestions)).toContain('Eggs')
    expect(names(filterIngredients(catalog, 'a cup of rice', none).suggestions)).toContain('Rice')
  })

  it('matches aliases', () => {
    expect(names(filterIngredients(catalog, 'extra virgin', none).suggestions)).toEqual([
      'Olive Oil',
    ])
  })

  it('never suggests something already in the pantry', () => {
    const owned = new Set([1])
    expect(names(filterIngredients(catalog, 'egg', owned).suggestions)).not.toContain('Eggs')
  })

  it('ranks prefix matches above substring matches', () => {
    const result = filterIngredients(catalog, 'oil', none)
    expect(names(result.suggestions)).toEqual(['Olive Oil'])
  })

  it('offers "did you mean" for a near miss, and no ordinary suggestions', () => {
    const result = filterIngredients(catalog, 'garlick', none)
    expect(result.suggestions).toEqual([])
    expect(names(result.didYouMean)).toEqual(['Garlic'])
  })

  it('offers nothing at all for text close to nothing', () => {
    const result = filterIngredients(catalog, 'zzzzz', none)
    expect(result.suggestions).toEqual([])
    expect(result.didYouMean).toEqual([])
  })

  it('is stricter about typos in short queries', () => {
    // "rise" is one edit from "rice", so it is offered.
    expect(names(filterIngredients(catalog, 'rise', none).didYouMean)).toEqual(['Rice'])
    // Two edits on a four-letter query is too far.
    expect(filterIngredients(catalog, 'rrse', none).didYouMean).toEqual([])
  })

  it('returns nothing for an empty query', () => {
    expect(filterIngredients(catalog, '   ', none)).toEqual({ suggestions: [], didYouMean: [] })
  })
})

describe('assumed staples', () => {
  it('never suggests water, because every kitchen is assumed to have it', () => {
    const withWater = [
      ...catalog,
      { id: 99, name: 'water', display_name: 'Water', aliases: [], recipe_count: 150 },
    ]

    const result = filterIngredients(withWater, 'water', new Set<number>())

    expect(result.suggestions).toEqual([])
    expect(result.didYouMean).toEqual([])
  })
})


describe('ranking', () => {
  const none = new Set<number>()

  it('offers the common ingredient before its rare variants', () => {
    const result = filterIngredients(catalog, 'egg', none)

    // Eggs is in 218 recipes; Egg Plants 9; Free-range Egg, Beaten 2. Alphabetical order
    // would have put Egg Plants first, which is what sent a real pantry to 40%.
    expect(names(result.suggestions)).toEqual(['Eggs', 'Egg Plants', 'Free-range Egg, Beaten'])
  })

  it('finds the singular ingredient when the plural is typed', () => {
    expect(names(filterIngredients(catalog, 'eggs', none).suggestions)[0]).toBe('Eggs')
    expect(names(filterIngredients(catalog, 'onions', none).suggestions)[0]).toBe('Onions')
    expect(names(filterIngredients(catalog, 'tomatoes', none).suggestions)[0]).toBe('Tomatoes')
  })

  it('still resolves an alias to its ingredient', () => {
    expect(names(filterIngredients(catalog, 'onion powder', none).suggestions)).toEqual(['Ground Onion'])
  })

  it('puts an exact match first, however rare it is', () => {
    // Typing the whole thing is an explicit choice, so it outranks popularity.
    expect(names(filterIngredients(catalog, 'ground onion', none).suggestions)[0]).toBe('Ground Onion')
  })
})
