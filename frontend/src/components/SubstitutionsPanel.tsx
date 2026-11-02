/**
 * "Suggest substitutions" and the panel it opens (F7, spec 10.11).
 *
 * Nothing is requested until the button is pressed: every press spends real money, so
 * there is no request on mount, no prefetch and no retry (spec 14).
 *
 * The panel is labelled and visually set apart from the recipe, because a model's
 * suggestion is not a recipe instruction and shouldn't be able to pass for one.
 */

import { useSubstitutions } from '../api/hooks'
import type { RecipeDetail, Substitution } from '../api/types'
import { AiProblem } from './AiNote'

export function SubstitutionsPanel({ recipe }: { recipe: RecipeDetail }) {
  const missing = recipe.ingredients.filter((ingredient) => !ingredient.owned)
  const substitutions = useSubstitutions(recipe.id)

  // No gap, no question. An absent button explains itself; a disabled one invites a click
  // and then says nothing.
  if (missing.length === 0) return null

  return (
    <div className="mt-7 border-t border-cream/15 pt-6">
      {!substitutions.data && !substitutions.isError && (
        <button
          type="button"
          onClick={() => substitutions.mutate()}
          disabled={substitutions.isPending}
          className="rounded-full bg-cream px-5 py-2 font-medium text-forest-dark transition hover:bg-cream-deep disabled:opacity-70"
        >
          {/* The label carries the wait: an Opus call takes a few seconds, and a button
              that looks unchanged reads as a button that didn't work. */}
          {substitutions.isPending ? 'Thinking…' : 'Suggest substitutions'}
        </button>
      )}

      <div aria-live="polite">
        {substitutions.isError && (
          <AiProblem
            error={substitutions.error}
            dailyLimit="You've used today's suggestions — try again tomorrow."
            failed="Couldn't get suggestions just now."
            onRetry={() => substitutions.mutate()}
          />
        )}

        {substitutions.data && <Suggestions suggestions={substitutions.data.suggestions} />}
      </div>
    </div>
  )
}

function Suggestions({ suggestions }: { suggestions: Substitution[] }) {
  return (
    <section className="rounded-2xl border border-dashed border-cream/30 bg-cream/10 p-5">
      <h3 className="mb-1 text-xs font-semibold tracking-[0.12em] uppercase">
        AI-generated suggestions
      </h3>
      <p className="mb-4 text-xs text-cream/65">
        Ideas, not instructions — taste as you go.
      </p>

      {suggestions.length === 0 ? (
        <p className="text-sm text-cream/85">
          No good substitutes for what&apos;s missing here. This one needs a shop.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {suggestions.map((suggestion) => (
            <li key={suggestion.missing_ingredient}>
              <p className="flex flex-wrap items-baseline gap-x-2 font-medium">
                <span className="text-cream/70">{suggestion.missing_ingredient}</span>
                <span aria-hidden="true" className="text-cream/50">
                  →
                </span>
                <span>{suggestion.suggestion}</span>
                {/* The most useful thing the panel can say, so it gets a mark of its own
                    rather than only a colour. */}
                {suggestion.in_pantry && (
                  <span className="rounded-full bg-cream/20 px-2 py-0.5 text-xs font-semibold">
                    in your pantry
                  </span>
                )}
              </p>
              <p className="text-sm text-cream/75">{suggestion.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/* The failure states and the dashed AI frame live in AiNote.tsx, shared with F8. */
