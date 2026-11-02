/**
 * The supermarkets a grocery list can link to (F9, spec 10.13).
 *
 * A table and one function — the whole "integration". No API, no key, and no call from
 * Scrappy's own server: the browser builds the URL and the user's click opens the
 * retailer's own search. F9 adds no third-party dependency to the running app.
 *
 * A chain that changes its URL format degrades to a search page that finds nothing, never
 * to a broken app, and fixing it is a one-line change here.
 *
 * **Mirrored file.** The keys below must match `STORE_KEYS` in `backend/app/stores.py`,
 * which validates `preferred_store`. `backend/tests/test_stores.py` reads this file and
 * fails if the two disagree, so a half-done change is caught rather than shipped.
 */

/** Chains in the order the picker shows them. */
export const STORES = [
  { key: 'walmart', name: 'Walmart', search: 'https://www.walmart.com/search?q={query}' },
  { key: 'target', name: 'Target', search: 'https://www.target.com/s?searchTerm={query}' },
  { key: 'kroger', name: 'Kroger', search: 'https://www.kroger.com/search?query={query}' },
  { key: 'heb', name: 'H-E-B', search: 'https://www.heb.com/search?q={query}' },
  { key: 'publix', name: 'Publix', search: 'https://www.publix.com/search?query={query}' },
  {
    key: 'safeway',
    name: 'Safeway',
    search: 'https://www.safeway.com/shop/search-results.html?q={query}',
  },
  {
    key: 'whole-foods',
    name: 'Whole Foods',
    search: 'https://www.wholefoodsmarket.com/search?text={query}',
  },
] as const

export type StoreKey = (typeof STORES)[number]['key']

/** The chain's display name, for the picker and the row's link text. */
export function storeName(store: StoreKey): string {
  return STORES.find((entry) => entry.key === store)!.name
}

/**
 * Where to send the shopper for one ingredient.
 *
 * `encodeURIComponent` rather than raw interpolation: ingredient names carry spaces and
 * the occasional comma or ampersand, any of which would otherwise cut the query short or
 * change what is being searched for.
 */
export function searchUrl(store: StoreKey, displayName: string): string {
  const entry = STORES.find((candidate) => candidate.key === store)
  if (!entry) return ''
  return entry.search.replace('{query}', encodeURIComponent(displayName))
}
