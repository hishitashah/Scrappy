/** All server state goes through these hooks (CLAUDE.md conventions). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { StoreKey } from '../lib/stores'
import { apiFetch } from './client'
import type {
  GroceryItem,
  Ingredient,
  Match,
  Me,
  PantryItem,
  RecipeDetail,
  SubstitutionsResponse,
} from './types'

export const queryKeys = {
  ingredients: ['ingredients'] as const,
  pantry: ['pantry'] as const,
  matches: ['matches'] as const,
  recipe: (id: number) => ['recipe', id] as const,
  groceryList: ['grocery-list'] as const,
  me: ['me'] as const,
}

/** The catalog is downloaded once per session and filtered in the browser (spec 10.1). */
export function useIngredients() {
  return useQuery({
    queryKey: queryKeys.ingredients,
    queryFn: () => apiFetch<Ingredient[]>('/ingredients'),
    staleTime: Infinity,
  })
}

export function usePantry() {
  return useQuery({
    queryKey: queryKeys.pantry,
    queryFn: () => apiFetch<PantryItem[]>('/pantry'),
  })
}

export function useMatches() {
  return useQuery({
    queryKey: queryKeys.matches,
    queryFn: () => apiFetch<Match[]>('/matches'),
  })
}

/** One query serves all three recipe pages, so advancing between them costs no request. */
export function useRecipe(id: number) {
  return useQuery({
    queryKey: queryKeys.recipe(id),
    queryFn: () => apiFetch<RecipeDetail>(`/recipes/${id}`),
    enabled: Number.isFinite(id),
    retry: false, // a 404 is an answer, not a failure worth retrying
  })
}

export function useAddPantryItems() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientIds: number[]) =>
      apiFetch<PantryItem[]>('/pantry/items', {
        method: 'POST',
        body: JSON.stringify({ ingredient_ids: ingredientIds }),
      }),
    onSuccess: (pantry) => {
      queryClient.setQueryData(queryKeys.pantry, pantry)
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pantry })
      void queryClient.invalidateQueries({ queryKey: queryKeys.matches })
      // The server deleted these from the grocery list in the same transaction — you
      // bought it, so it is no longer something to buy (spec 10.13). Without this the
      // list keeps showing it until something else happens to refetch.
      void queryClient.invalidateQueries({ queryKey: queryKeys.groceryList })
      // Every recipe's `owned` flags and "you have 4 of 6" just changed. The prefix
      // matches every `['recipe', id]`, because an ingredient added from one recipe's
      // page is owned on all of them — and it is what makes "I have this" remove the
      // row it was pressed on (spec 10.11).
      void queryClient.invalidateQueries({ queryKey: ['recipe'] })
    },
  })
}

/**
 * Remove an ingredient optimistically (spec 10.1): the chip disappears at once, and
 * comes back if the server rejects the change.
 */
export function useRemovePantryItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientId: number) =>
      apiFetch<void>(`/pantry/items/${ingredientId}`, { method: 'DELETE' }),
    onMutate: async (ingredientId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.pantry })
      const previous = queryClient.getQueryData<PantryItem[]>(queryKeys.pantry)
      queryClient.setQueryData<PantryItem[]>(queryKeys.pantry, (pantry) =>
        (pantry ?? []).filter((item) => item.ingredient_id !== ingredientId),
      )
      return { previous }
    },
    onError: (_error, _ingredientId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.pantry, context.previous)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.pantry })
      void queryClient.invalidateQueries({ queryKey: queryKeys.matches })
    },
  })
}

export function useGroceryList() {
  return useQuery({
    queryKey: queryKeys.groceryList,
    queryFn: () => apiFetch<GroceryItem[]>('/grocery-list'),
  })
}

/** Add one ingredient or many: the API takes up to 50 ids in a single call (spec 10.13). */
export function useAddGroceryItems() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientIds: number[]) =>
      apiFetch<GroceryItem[]>('/grocery-list/items', {
        method: 'POST',
        body: JSON.stringify({ ingredient_ids: ingredientIds }),
      }),
    onSuccess: (list) => {
      queryClient.setQueryData(queryKeys.groceryList, list)
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.groceryList })
    },
  })
}

/** Optimistic, like the pantry's removal: the row goes at once and returns on failure. */
export function useRemoveGroceryItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientId: number) =>
      apiFetch<void>(`/grocery-list/items/${ingredientId}`, { method: 'DELETE' }),
    onMutate: async (ingredientId) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.groceryList })
      const previous = queryClient.getQueryData<GroceryItem[]>(queryKeys.groceryList)
      queryClient.setQueryData<GroceryItem[]>(queryKeys.groceryList, (list) =>
        (list ?? []).filter((item) => item.ingredient_id !== ingredientId),
      )
      return { previous }
    },
    onError: (_error, _ingredientId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.groceryList, context.previous)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.groceryList })
    },
  })
}

/**
 * Empty the list in one request (spec 10.13).
 *
 * One call rather than one delete per row: a loop can fail halfway and leave the list
 * partly cleared, which is a state nothing else in the app can produce.
 */
export function useClearGroceryList() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<void>('/grocery-list', { method: 'DELETE' }),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: queryKeys.groceryList })
      const previous = queryClient.getQueryData<GroceryItem[]>(queryKeys.groceryList)
      queryClient.setQueryData<GroceryItem[]>(queryKeys.groceryList, [])
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.groceryList, context.previous)
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.groceryList })
    },
  })
}

export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => apiFetch<Me>('/me'),
  })
}

/**
 * Choose which supermarket the list links to (spec 10.13).
 *
 * Stored on the server rather than in the browser, so the choice follows the user between
 * devices as their pantry does.
 */
export function useSetPreferredStore() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (store: StoreKey | null) =>
      apiFetch<Me>('/me', {
        method: 'PATCH',
        body: JSON.stringify({ preferred_store: store }),
      }),
    onSuccess: (me) => {
      queryClient.setQueryData(queryKeys.me, me)
    },
  })
}

/**
 * Ask for substitutions for one recipe's missing ingredients (F7, spec 10.11).
 *
 * A mutation rather than a query, and that is the whole point: a query runs on mount, and
 * every call here spends money (spec 14). A mutation runs only when something calls
 * `mutate` — which is the button, and nothing else.
 *
 * Deliberately absent from `queryKeys`: the answer belongs to the press rather than to the
 * cache, so navigating away forgets it. Pressing again costs a round trip but no money,
 * because the server already has the answer cached.
 */
export function useSubstitutions(recipeId: number) {
  return useMutation({
    // The ids are the ticked checkboxes (spec 10.11). The server intersects them with what
    // it computed as missing, so this narrows the question and cannot widen it — sending a
    // shorter list is the only way to spend less, which is why the filtering is not done
    // here after the fact.
    mutationFn: (ingredientIds: number[]) =>
      apiFetch<SubstitutionsResponse>(`/recipes/${recipeId}/substitutions`, {
        method: 'POST',
        body: JSON.stringify({ ingredient_ids: ingredientIds }),
      }),
  })
}

/**
 * Write a recipe from the pantry and save it to the account (F8, spec 10.12).
 *
 * A mutation for the same reason as above: a query would run on mount, and this spends
 * money. The server reads the pantry itself, so there is no body to send.
 */
export function useGenerateRecipe() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<RecipeDetail>('/recipes/generate', { method: 'POST' }),
    onSuccess: (recipe) => {
      // The page we're about to navigate to reads this key, so seeding it renders the
      // recipe we just paid for instead of fetching it a second time behind a skeleton.
      queryClient.setQueryData(queryKeys.recipe(recipe.id), recipe)
      // And it belongs in the results list we came from, where it is a complete match.
      void queryClient.invalidateQueries({ queryKey: queryKeys.matches })
    },
  })
}
