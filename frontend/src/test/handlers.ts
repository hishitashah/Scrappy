import { HttpResponse, http } from 'msw'

import type {
  GroceryItem,
  Ingredient,
  Match,
  PantryItem,
  RecipeDetail,
  SubstitutionsResponse,
} from '../api/types'
import type { StoreKey } from '../lib/stores'

const API = 'http://localhost:8000'

export const catalog: Ingredient[] = [
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
  { id: 5, name: 'salt', display_name: 'Salt', aliases: [], recipe_count: 400 },
  { id: 6, name: 'water', display_name: 'Water', aliases: [], recipe_count: 150 },
]

/** Mutable per-test pantry state, reset by `resetPantry`. */
let pantry: PantryItem[] = []
let matches: Match[] = []
let groceryList: GroceryItem[] = []
let preferredStore: StoreKey | null = null

export function resetPantry(items: PantryItem[] = []) {
  pantry = [...items]
}

export function resetGroceryList(items: GroceryItem[] = []) {
  groceryList = [...items]
}

/** Null is the real starting state: no store is chosen on the user's behalf. */
export function resetMe(store: StoreKey | null = null) {
  preferredStore = store
}

export function groceryItem(ingredientId: number): GroceryItem {
  const ingredient = catalog.find((entry) => entry.id === ingredientId)!
  return {
    ingredient_id: ingredient.id,
    display_name: ingredient.display_name,
    added_at: '2026-11-02T00:00:00Z',
  }
}

export function resetMatches(rows: Match[] = []) {
  matches = [...rows]
}

export function match(overrides: Partial<Match> = {}): Match {
  return {
    id: 1,
    title: 'Egg fried rice',
    thumbnail_url: 'https://example.test/egg-fried-rice.jpg',
    have: 3,
    total: 7,
    match: 43,
    missing: ['Oil', 'Salt', 'Soy Sauce', 'Spring Onion'],
    generated: false,
    ...overrides,
  }
}

export function pantryItem(ingredientId: number): PantryItem {
  const ingredient = catalog.find((entry) => entry.id === ingredientId)!
  return {
    ingredient_id: ingredient.id,
    display_name: ingredient.display_name,
    added_at: '2026-09-26T00:00:00Z',
  }
}

/** A fixture recipe: 4 of 6 owned, so the count line and both row styles are exercised. */
export function recipe(overrides: Partial<RecipeDetail> = {}): RecipeDetail {
  return {
    id: 42,
    title: 'Egg fried rice',
    category: 'Rice',
    area: 'Chinese',
    image_url: 'https://example.test/egg-fried-rice.jpg',
    youtube_url: 'https://example.test/video',
    source_url: 'https://example.test/source',
    steps: ['Boil the rice.', 'Fry the eggs.', 'Combine and serve.'],
    generated: false,
    ingredients: [
      { id: 2, display_name: 'Rice', measure: '2 cups', owned: true },
      { id: 1, display_name: 'Egg', measure: '3', owned: true },
      { id: 3, display_name: 'Garlic', measure: '2 cloves', owned: true },
      { id: 6, display_name: 'Water', measure: '1 cup', owned: true },
      { id: 4, display_name: 'Olive Oil', measure: '1 tbsp', owned: false },
      { id: 5, display_name: 'Salt', measure: null, owned: false },
    ],
    ...overrides,
  }
}

/**
 * What `POST /recipes/generate` answers with (F8): no category, cuisine, photo, video or
 * source, because a generated recipe has none and invents none.
 */
export function generatedRecipe(overrides: Partial<RecipeDetail> = {}): RecipeDetail {
  return recipe({
    id: 51,
    title: 'Garlic Fried Rice',
    category: null,
    area: null,
    image_url: null,
    youtube_url: null,
    source_url: null,
    generated: true,
    ...overrides,
  })
}

let recipeDetail: RecipeDetail | null = recipe()

export function resetRecipe(next: RecipeDetail | null = recipe()) {
  recipeDetail = next
}

/**
 * Substitutions for the fixture recipe's two missing ingredients (Olive Oil, Salt), one of
 * which the cook already has — so both row styles are exercised.
 */
export function substitutions(
  overrides: Partial<SubstitutionsResponse> = {},
): SubstitutionsResponse {
  return {
    suggestions: [
      {
        missing_ingredient: 'Olive Oil',
        suggestion: 'Butter',
        reason: 'Both carry heat and add richness.',
        in_pantry: false,
      },
      {
        missing_ingredient: 'Salt',
        suggestion: 'Garlic',
        reason: 'Seasons the dish without the salt.',
        in_pantry: true,
      },
    ],
    ...overrides,
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
    // The real endpoint deletes these from the grocery list in the same transaction
    // (spec 10.13). Mirrored here, or a test for that behaviour would prove nothing.
    groceryList = groceryList.filter((item) => !body.ingredient_ids.includes(item.ingredient_id))
    // `owned` is computed from the pantry server-side, so an ingredient just added is
    // owned the next time the recipe is read. Mirrored for the same reason: without it,
    // "I have this" could appear to work while the row it removed never came back owned.
    if (recipeDetail) {
      recipeDetail = {
        ...recipeDetail,
        ingredients: recipeDetail.ingredients.map((ingredient) =>
          body.ingredient_ids.includes(ingredient.id) ? { ...ingredient, owned: true } : ingredient,
        ),
      }
    }
    return HttpResponse.json(pantry)
  }),
  http.delete(`${API}/pantry/items/:id`, ({ params }) => {
    pantry = pantry.filter((item) => item.ingredient_id !== Number(params['id']))
    return new HttpResponse(null, { status: 204 })
  }),
  http.get(`${API}/matches`, () => HttpResponse.json(matches)),
  http.get(`${API}/recipes/:id`, () =>
    recipeDetail
      ? HttpResponse.json(recipeDetail)
      : HttpResponse.json({ detail: 'Recipe not found' }, { status: 404 }),
  ),
  // Tests that care about the AI calls override these; they exist so that an accidental
  // request fails a test loudly rather than tripping MSW's unhandled-request error.
  http.post(`${API}/recipes/:id/substitutions`, () => HttpResponse.json(substitutions())),
  http.post(`${API}/recipes/generate`, () => HttpResponse.json(generatedRecipe())),

  http.get(`${API}/grocery-list`, () => HttpResponse.json(groceryList)),
  http.post(`${API}/grocery-list/items`, async ({ request }) => {
    const body = (await request.json()) as { ingredient_ids: number[] }
    for (const id of body.ingredient_ids) {
      if (!groceryList.some((item) => item.ingredient_id === id)) groceryList.push(groceryItem(id))
    }
    groceryList.sort((a, b) => a.display_name.localeCompare(b.display_name))
    return HttpResponse.json(groceryList)
  }),
  http.delete(`${API}/grocery-list/items/:id`, ({ params }) => {
    groceryList = groceryList.filter((item) => item.ingredient_id !== Number(params['id']))
    return new HttpResponse(null, { status: 204 })
  }),
  http.delete(`${API}/grocery-list`, () => {
    groceryList = []
    return new HttpResponse(null, { status: 204 })
  }),

  http.get(`${API}/me`, () => HttpResponse.json({ preferred_store: preferredStore })),
  http.patch(`${API}/me`, async ({ request }) => {
    const body = (await request.json()) as { preferred_store: StoreKey | null }
    preferredStore = body.preferred_store
    return HttpResponse.json({ preferred_store: preferredStore })
  }),
]
