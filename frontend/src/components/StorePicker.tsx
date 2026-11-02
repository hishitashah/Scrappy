/**
 * Which supermarket the grocery list links to (F9, spec 10.13).
 *
 * Sits on the cream field above the list's card, so it is styled like the pantry's
 * combobox — a white control with a forest edge — rather than like the card's contents.
 *
 * The choice is written through `PATCH /me`, not kept in the browser, so it follows the
 * user between devices as their pantry does.
 */

import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/react'

import { useMe, useSetPreferredStore } from '../api/hooks'
import { STORES, type StoreKey, storeName } from '../lib/stores'

export function StorePicker() {
  const me = useMe()
  const setStore = useSetPreferredStore()

  // `undefined` rather than null: Listbox reads that as "nothing selected". The API's null
  // means the same thing, so it is converted here instead of leaking into the component.
  const current = me.data?.preferred_store ?? undefined

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted">Shopping at</span>

      <Listbox
        value={current}
        onChange={(store: StoreKey) => setStore.mutate(store)}
        disabled={me.isPending}
      >
        <div className="relative">
          <ListboxButton
            aria-label="Choose a store"
            className="flex min-w-44 items-center justify-between gap-3 rounded-full border border-forest/20 bg-white px-5 py-2 text-left text-sm font-medium text-ink shadow-sm transition hover:border-forest disabled:opacity-60"
          >
            {/* Null reads as a prompt, not as a chain: nothing is chosen on the user's
                behalf, so the list's rows say "Pick a store" until one is. */}
            {current ? storeName(current) : 'Pick a store'}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M6 9l6 6 6-6"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </ListboxButton>

          <ListboxOptions className="absolute left-0 z-20 mt-2 w-full overflow-hidden rounded-3xl border border-olive/20 bg-white py-2 shadow-lg">
            {STORES.map((store) => (
              <ListboxOption
                key={store.key}
                value={store.key}
                className="cursor-pointer px-5 py-2 text-sm text-ink data-focus:bg-forest-light data-selected:font-semibold"
              >
                {store.name}
              </ListboxOption>
            ))}
          </ListboxOptions>
        </div>
      </Listbox>
    </div>
  )
}
