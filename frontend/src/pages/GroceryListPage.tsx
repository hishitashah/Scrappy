/**
 * `/list` — what's left to buy, and where to buy it (F9, spec 10.13).
 *
 * The shopping end of the app: everything here was added from a recipe's missing
 * ingredients, and everything leaves either by being bought (adding it to the pantry
 * deletes it, server-side) or by being removed here.
 *
 * Scrappy never talks to a retailer. Each row's link is built in the browser from the
 * table in `lib/stores.ts` and opened by the user's own click.
 */

import { useState } from 'react'

import { useClearGroceryList, useGroceryList, useMe, useRemoveGroceryItem } from '../api/hooks'
import type { GroceryItem } from '../api/types'
import { PageShell } from '../components/PageShell'
import { StorePicker } from '../components/StorePicker'
import { type StoreKey, searchUrl, storeName } from '../lib/stores'

export function GroceryListPage() {
  const list = useGroceryList()
  const me = useMe()
  const removeItem = useRemoveGroceryItem()

  const store = me.data?.preferred_store ?? null

  return (
    <PageShell heading="Grocery list" above={<StorePicker />}>
      {removeItem.isError && (
        <p role="alert" className="mb-4 text-sm text-cream">
          Couldn&apos;t remove that item. Please try again.
        </p>
      )}

      {list.isPending ? (
        <ListSkeleton />
      ) : list.isError ? (
        <div className="text-sm text-cream/85">
          <p className="mb-3">Couldn&apos;t load your list.</p>
          <button
            type="button"
            onClick={() => void list.refetch()}
            className="rounded-full bg-cream px-4 py-1.5 font-medium text-forest-dark"
          >
            Try again
          </button>
        </div>
      ) : list.data.length === 0 ? (
        <p className="text-cream/85">
          Nothing to buy yet. Open a recipe and add what you&apos;re missing.
        </p>
      ) : (
        <>
          <ul className="flex flex-col divide-y divide-cream/15">
            {list.data.map((item) => (
              <Row
                key={item.ingredient_id}
                item={item}
                store={store}
                onRemove={() => removeItem.mutate(item.ingredient_id)}
              />
            ))}
          </ul>
          <ClearListButton />
        </>
      )}
    </PageShell>
  )
}

function Row({
  item,
  store,
  onRemove,
}: {
  item: GroceryItem
  store: StoreKey | null
  onRemove: () => void
}) {
  return (
    <li className="flex items-center gap-3 py-3">
      <span className="font-medium">{item.display_name}</span>

      <span className="ml-auto flex shrink-0 items-center gap-4">
        {store ? (
          <a
            href={searchUrl(store, item.display_name)}
            target="_blank"
            // noreferrer, not just noopener: the retailer has no business knowing which
            // page sent the shopper (spec 10.13).
            rel="noreferrer"
            className="text-sm font-medium underline decoration-cream/40 hover:decoration-cream"
          >
            Find at {storeName(store)}
          </a>
        ) : (
          // A cue pointing at the picker above, rather than a link that goes nowhere.
          <span className="text-sm text-cream/60">Pick a store</span>
        )}

        <button
          type="button"
          aria-label={`Remove ${item.display_name}`}
          onClick={onRemove}
          className="text-cream/60 transition hover:text-cream"
        >
          ×
        </button>
      </span>
    </li>
  )
}

/**
 * "Clear list", as a two-step confirm.
 *
 * Emptying a long list by a stray click would be the one unrecoverable action in the app —
 * the items can only be restored by remembering them and re-adding each one. A second
 * press is cheap; `onBlur` resets, so an abandoned first press leaves nothing armed.
 */
function ClearListButton() {
  const [armed, setArmed] = useState(false)
  const clearList = useClearGroceryList()

  return (
    <div className="mt-5">
      <button
        type="button"
        onClick={() => {
          if (armed) {
            clearList.mutate()
            setArmed(false)
          } else {
            setArmed(true)
          }
        }}
        onBlur={() => setArmed(false)}
        className="text-sm font-medium text-cream/70 underline transition hover:text-cream"
      >
        {armed ? 'Clear the whole list?' : 'Clear list'}
      </button>
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden="true" data-testid="grocery-skeleton">
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="h-4 animate-pulse rounded-full bg-cream/20" />
      ))}
    </div>
  )
}
