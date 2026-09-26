/** All server state goes through these hooks (CLAUDE.md conventions). */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from './client'
import type { Ingredient, Match, PantryItem } from './types'

export const queryKeys = {
  ingredients: ['ingredients'] as const,
  pantry: ['pantry'] as const,
  matches: ['matches'] as const,
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
