/**
 * The frame the inner pages share (spec section 6, following the mockups in `docs/`):
 * a black uppercase heading on the cream field at the left, the content in a rounded
 * forest card at the right.
 *
 * Used by the three recipe pages through `RecipePageFrame`, which adds their loading,
 * error and 404 behaviour, and directly by the grocery list. Extracted so the heading and
 * the card are decided once — two pages that are meant to look identical shouldn't each
 * carry their own copy of the grid.
 */

import type { ReactNode } from 'react'

interface Props {
  heading: ReactNode
  /** The right column, above the card, on the cream field. The grocery list's store picker. */
  above?: ReactNode
  children: ReactNode
  /** Below the card: the recipe flow's chevrons. */
  footer?: ReactNode
}

export function PageShell({ heading, above, children, footer }: Props) {
  return (
    <div className="grid grid-cols-[1fr_minmax(420px,620px)] items-center gap-10">
      <h2 className="font-display text-6xl leading-[0.95] font-extrabold tracking-tight uppercase">
        {heading}
      </h2>
      <div>
        {above && <div className="mb-5">{above}</div>}
        <div className="rounded-card border border-olive/40 bg-forest p-9 text-cream">
          {children}
        </div>
        {footer && <div className="mt-5 flex items-center justify-between gap-4">{footer}</div>}
      </div>
    </div>
  )
}
