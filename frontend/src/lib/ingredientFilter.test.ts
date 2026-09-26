import { describe, expect, it } from 'vitest'

import type { Ingredient } from '../api/types'
import { filterIngredients, stripQuantityWords } from './ingredientFilter'

const catalog: Ingredient[] = [
  { id: 1, name: 'egg', display_name: 'Egg', aliases: ['eggs'] },
  { id: 2, name: 'rice', display_name: 'Rice', aliases: [] },
  { id: 3, name: 'garlic', display_name: 'Garlic', aliases: ['garlic clove'] },
  { id: 4, name: 'olive oil', display_name: 'Olive Oil', aliases: ['extra virgin olive oil'] },
  { id: 5, name: 'tomato', display_name: 'Tomato', aliases: [] },
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
    expect(names(filterIngredients(catalog, 'egg', none).suggestions)).toContain('Egg')
  })

  it('still suggests Egg for "1 egg" and Rice for "a cup of rice"', () => {
    expect(names(filterIngredients(catalog, '1 egg', none).suggestions)).toContain('Egg')
    expect(names(filterIngredients(catalog, 'a cup of rice', none).suggestions)).toContain('Rice')
  })

  it('matches aliases', () => {
    expect(names(filterIngredients(catalog, 'extra virgin', none).suggestions)).toEqual([
      'Olive Oil',
    ])
  })

  it('never suggests something already in the pantry', () => {
    const owned = new Set([1])
    expect(names(filterIngredients(catalog, 'egg', owned).suggestions)).not.toContain('Egg')
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
    const withWater = [...catalog, { id: 9, name: 'water', display_name: 'Water', aliases: [] }]

    const result = filterIngredients(withWater, 'water', new Set<number>())

    expect(result.suggestions).toEqual([])
    expect(result.didYouMean).toEqual([])
  })
})
