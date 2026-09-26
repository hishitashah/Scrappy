/** The page chrome from docs/current background.png: cream field, menu button, mascot. */

import { Menu, MenuButton as HeadlessMenuButton, MenuItem, MenuItems } from '@headlessui/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

export function AppFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-cream">
      <div className="mx-auto max-w-[1180px] px-10 py-8">
        <header className="mb-8 flex items-start justify-between gap-8">
          <div className="flex items-start gap-6">
            <AppMenu />
            <div>
              <h1 className="font-display text-5xl font-extrabold tracking-tight">SCRAPPY</h1>
              <p className="mt-2 max-w-sm text-sm text-muted">
                Quick, simple meals from what you already have
              </p>
            </div>
          </div>

          {/* Decoration, so it is hidden from assistive technology. */}
          <img
            src="/mascot.png"
            alt=""
            aria-hidden="true"
            className="-mt-4 w-[230px] shrink-0 select-none"
          />
        </header>

        <main>{children}</main>
      </div>
    </div>
  )
}

function AppMenu() {
  return (
    <Menu as="div" className="relative mt-1 shrink-0">
      <HeadlessMenuButton
        aria-label="Menu"
        className="flex size-14 items-center justify-center rounded-full bg-forest text-cream transition hover:bg-forest-dark"
      >
      <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
        <circle cx="5" cy="6" r="1.4" />
        <circle cx="5" cy="12" r="1.4" />
        <circle cx="5" cy="18" r="1.4" />
        <rect x="9" y="5" width="11" height="2" rx="1" />
        <rect x="9" y="11" width="11" height="2" rx="1" />
        <rect x="9" y="17" width="11" height="2" rx="1" />
      </svg>
      </HeadlessMenuButton>

      <MenuItems className="absolute left-0 z-20 mt-2 w-44 overflow-hidden rounded-3xl border border-olive/20 bg-white py-2 shadow-lg">
        <MenuItem>
          <Link to="/" className="block px-5 py-2.5 text-ink data-focus:bg-forest-light">
            Home
          </Link>
        </MenuItem>
        <MenuItem>
          {/* Signing out needs Cognito, which arrives in M5 (spec 10.4). */}
          <button
            type="button"
            disabled
            title="Available once login ships"
            className="block w-full cursor-not-allowed px-5 py-2.5 text-left text-muted/60"
          >
            Log out
          </button>
        </MenuItem>
      </MenuItems>
    </Menu>
  )
}
