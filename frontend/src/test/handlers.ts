import { HttpResponse, http } from 'msw'

import type { Ingredient, PantryItem } from '../api/types'

const API = 'http://localhost:8000'

export const catalog: Ingredient[] = [
  { id: 1, name: 'egg', display_name: 'Egg', aliases: ['eggs'] },
  { id: 2, name: 'rice', display_name: 'Rice', aliases: [] },
  { id: 3, name: 'garlic', display_name: 'Garlic', aliases: ['garlic clove'] },
  { id: 4, name: 'olive oil', display_name: 'Olive Oil', aliases: ['extra virgin olive oil'] },
  { id: 5, name: 'salt', display_name: 'Salt', aliases: [] },
  { id: 6, name: 'water', display_name: 'Water', aliases: [] },
]

/** Mutable per-test pantry state, reset by `resetPantry`. */
let pantry: PantryItem[] = []

export function resetPantry(items: PantryItem[] = []) {
  pantry = [...items]
}

export function pantryItem(ingredientId: number): PantryItem {
  const ingredient = catalog.find((entry) => entry.id === ingredientId)!
  return {
    ingredient_id: ingredient.id,
    display_name: ingredient.display_name,
    added_at: '2026-09-26T00:00:00Z',
  }
}

export const handlers = [
  http.get(`${API}/ingredients`, () => HttpResponse.json(catalog)),
  http.get(`${API}/pantry`, () => HttpResponse.json(pantry)),
  http.post(`${API}/pantry/items`, async ({ request }) => {
    const body = (await request.json()) as { ingredient_ids: number[] }
    for (const id of body.ingredient_ids) {
      if (!pantry.some((item) => item.ingredient_id === id)) pantry.push(pantryItem(id))
    }
    pantry.sort((a, b) => a.display_name.localeCompare(b.display_name))
    return HttpResponse.json(pantry)
  }),
  http.delete(`${API}/pantry/items/:id`, ({ params }) => {
    pantry = pantry.filter((item) => item.ingredient_id !== Number(params['id']))
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${API}/matches`, () => HttpResponse.json([])),
]
