/**
 * "Generate a recipe from my ingredients" (F8, spec 10.12).
 *
 * Shown whenever the pantry holds at least one ingredient, above the results.
 *
 * It used to appear only in dead ends — nothing matched, or nothing matched as a meal — on
 * the assumption that a generated recipe is what you want when there is nothing to cook.
 * That reads the need too narrowly: a cook can have twenty matches and fancy none of them,
 * and wanting something different is not the same as having nothing. Being reachable only
 * from a dead end also hid the feature entirely from anyone whose pantry matched anything.
 *
 * Still withheld on an empty pantry: there is nothing to build from, and the endpoint says
 * so with a 422.
 *
 * Nothing is requested until the button is pressed: every press spends real money, so
 * there is no request on mount, no prefetch and no retry (spec 14).
 */

import { useNavigate } from 'react-router'

import { useGenerateRecipe } from '../api/hooks'
import { AiProblem } from './AiNote'

export function GenerateRecipeButton() {
  const navigate = useNavigate()
  const generate = useGenerateRecipe()

  function press() {
    generate.mutate(undefined, {
      // Navigation lives here rather than in the hook: the hook caches the recipe, and
      // where to go next is this screen's business.
      onSuccess: (recipe) => void navigate(`/recipes/${recipe.id}`),
    })
  }

  return (
    <div>
      {!generate.isError && (
        <button
          type="button"
          onClick={press}
          disabled={generate.isPending}
          className="rounded-full bg-cream px-5 py-2 font-medium text-forest-dark transition hover:bg-cream-deep disabled:opacity-70"
        >
          {/* The label carries the wait: writing a whole recipe takes several seconds, and
              a button that looks unchanged reads as a button that didn't work. */}
          {generate.isPending ? 'Writing a recipe…' : 'Generate a recipe from my ingredients'}
        </button>
      )}

      <div aria-live="polite">
        {generate.isError && (
          <AiProblem
            error={generate.error}
            dailyLimit="You've used today's recipes — try again tomorrow."
            failed="Couldn't write a recipe just now."
            onRetry={press}
          />
        )}
      </div>
    </div>
  )
}
