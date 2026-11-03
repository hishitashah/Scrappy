/**
 * "Suggest substitutions" and the panel it opens (F7, spec 10.11).
 *
 * Nothing is requested until the button is pressed: every press spends real money, so
 * there is no request on mount, no prefetch and no retry (spec 14).
 *
 * The panel is labelled and visually set apart from the recipe, because a model's
 * suggestion is not a recipe instruction and shouldn't be able to pass for one.
 *
 * A gap is not always a problem worth solving, so the cook chooses which ones to ask
 * about. Two different reasons to leave one out, and the panel offers both:
 *
 * - they'll cook without it — untick the box, and it isn't asked about or paid for.
 * - they do have it and never typed it in — "I have this" puts it in the pantry, which
 *   fixes the gap everywhere rather than hiding it here. Unticking would leave the recipe
 *   still reporting "you have 4 of 6" and the grocery list still offering to buy it.
 */

import { useState } from "react";

import { useAddPantryItems, useSubstitutions } from "../api/hooks";
import type {
  RecipeDetail,
  RecipeIngredient,
  Substitution,
} from "../api/types";
import { AiProblem } from "./AiNote";

export function SubstitutionsPanel({ recipe }: { recipe: RecipeDetail }) {
  const missing = recipe.ingredients.filter((ingredient) => !ingredient.owned);
  const substitutions = useSubstitutions(recipe.id);

  // Which boxes are *un*ticked, rather than which are ticked. Everything is asked about by
  // default, and that stays true for a row this component has not seen before: an
  // ingredient arriving in a refetch is included without the state having to be rebuilt,
  // and one that leaves — because "I have this" was pressed — takes nothing stale with it.
  const [excluded, setExcluded] = useState<ReadonlySet<number>>(new Set());

  const asked = missing.filter((ingredient) => !excluded.has(ingredient.id));

  // No gap, no question. An absent button explains itself; a disabled one invites a click
  // and then says nothing.
  if (missing.length === 0) return null;

  const toggle = (id: number) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <div className="mt-7 border-t border-cream/15 pt-6">
      {!substitutions.data && !substitutions.isError && (
        <>
          <MissingPicker
            missing={missing}
            excluded={excluded}
            onToggle={toggle}
            disabled={substitutions.isPending}
          />

          <button
            type="button"
            onClick={() =>
              substitutions.mutate(asked.map((ingredient) => ingredient.id))
            }
            disabled={substitutions.isPending || asked.length === 0}
            className="mt-4 rounded-full bg-cream px-5 py-2 font-medium text-forest-dark transition hover:bg-cream-deep disabled:opacity-70"
          >
            {/* The label carries the wait: an Opus call takes a few seconds, and a button
                that looks unchanged reads as a button that didn't work. */}
            {substitutions.isPending
              ? "Thinking…"
              : /* The count appears only once the cook has narrowed it down, so the
                   ordinary case keeps the plain label it has always had. */
                asked.length === missing.length
                ? "Suggest substitutions"
                : `Suggest substitutions for ${asked.length}`}
          </button>

          {asked.length === 0 && (
            <p className="mt-2 text-xs text-cream/65">
              Tick something to ask about, or add what you have to your pantry.
            </p>
          )}
        </>
      )}

      <div aria-live="polite">
        {substitutions.isError && (
          <AiProblem
            error={substitutions.error}
            dailyLimit="You've used today's suggestions — try again tomorrow."
            failed="Couldn't get suggestions just now."
            onRetry={() =>
              substitutions.mutate(asked.map((ingredient) => ingredient.id))
            }
          />
        )}

        {substitutions.data && (
          <Suggestions suggestions={substitutions.data.suggestions} />
        )}
      </div>
    </div>
  );
}

/** The missing ingredients, each with a box to untick and a way to say "I have this". */
function MissingPicker({
  missing,
  excluded,
  onToggle,
  disabled,
}: {
  missing: RecipeIngredient[];
  excluded: ReadonlySet<number>;
  onToggle: (id: number) => void;
  disabled: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="disabled:opacity-60">
      <legend className="mb-3 text-xs font-semibold tracking-[0.12em] uppercase">
        What to substitute
      </legend>

      {/* Named as well as grouped: the legend labels the fieldset, so without this the
          list itself has no accessible name to distinguish it from the recipe's own. */}
      <ul aria-label="What to substitute" className="flex flex-col gap-1.5">
        {missing.map((ingredient) => (
          <li key={ingredient.id} className="flex items-center gap-3">
            <label className="flex flex-1 cursor-pointer items-center gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={!excluded.has(ingredient.id)}
                onChange={() => onToggle(ingredient.id)}
                className="size-4 shrink-0 accent-cream"
              />
              <span
                className={
                  excluded.has(ingredient.id) ? "text-cream/50" : undefined
                }
              >
                {ingredient.display_name}
              </span>
            </label>

            <HaveThisButton ingredient={ingredient} />
          </li>
        ))}
      </ul>
    </fieldset>
  );
}

/**
 * "I have this" — the cook owns it, they just hadn't typed it in (spec 10.1, 10.11).
 *
 * It writes to the pantry, so the row disappears from this list on the refetch, the
 * recipe's own count corrects itself, and the ingredient stops being offered for the
 * grocery list. That is the point of doing it here rather than unticking a box.
 */
function HaveThisButton({ ingredient }: { ingredient: RecipeIngredient }) {
  const addItems = useAddPantryItems();

  return (
    <button
      type="button"
      onClick={() => addItems.mutate([ingredient.id])}
      disabled={addItems.isPending}
      className="shrink-0 rounded-full border border-cream/40 px-2 py-0.5 text-[0.6875rem] font-medium transition hover:bg-cream/15 disabled:opacity-70"
    >
      I have this
    </button>
  );
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
          No good substitutes for what&apos;s missing here. This one needs a
          shop.
        </p>
      ) : (
        <ul className="flex flex-col gap-4">
          {suggestions.map((suggestion) => (
            <li key={suggestion.missing_ingredient}>
              <p className="flex flex-wrap items-baseline gap-x-2 font-medium">
                <span className="text-cream/70">
                  {suggestion.missing_ingredient}
                </span>
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
  );
}

/* The failure states and the dashed AI frame live in AiNote.tsx, shared with F8. */
