/** Ranked recipe results (spec 10.2). Updates automatically after any pantry change. */

import { Link } from 'react-router'

import { useMatches, usePantry } from '../api/hooks'
import type { Match } from '../api/types'

export function ResultsList() {
  const pantry = usePantry()
  const matches = useMatches()

  const pantryIsEmpty = (pantry.data ?? []).length === 0

  return (
    <section className="rounded-card bg-forest p-8 text-cream">
      <h2 className="mb-6 font-display text-2xl font-bold tracking-tight">What you can make</h2>

      {matches.isPending || pantry.isPending ? (
        <ResultsSkeleton />
      ) : matches.isError ? (
        <div className="text-sm text-cream/85">
          <p className="mb-3">Couldn&apos;t load your matches.</p>
          <button
            type="button"
            onClick={() => void matches.refetch()}
            className="rounded-full bg-cream px-4 py-1.5 font-medium text-forest-dark"
          >
            Try again
          </button>
        </div>
      ) : matches.data.length === 0 ? (
        // Two distinct empty states (spec US-5), chosen by whether the pantry is empty.
        // Recipes under 50% are hidden, so the second message can't promise "no recipes use
        // these ingredients" — it says what actually helps: add a few more.
        <p className="text-cream/85">
          {pantryIsEmpty
            ? 'Add a few ingredients to see what you can make.'
            : "Nothing's close enough yet. Add a few more ingredients."}
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {matches.data.map((match) => (
            <li key={match.id}>
              <RecipeCard match={match} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function RecipeCard({ match }: { match: Match }) {
  return (
    <Link
      to={`/recipes/${match.id}`}
      className="block rounded-3xl bg-cream/10 px-5 py-4 transition hover:bg-cream/20"
    >
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-3">
          <span className="truncate font-semibold">{match.title}</span>
          <span className="shrink-0 rounded-full bg-cream px-2.5 py-0.5 text-xs font-bold text-forest-dark">
            {match.match}%
          </span>
        </div>
        <p className="mt-0.5 text-sm text-cream/85">
          You have {match.have} of {match.total}
        </p>
        {match.missing.length > 0 && (
          <p className="mt-0.5 truncate text-sm text-cream/70">
            Missing: {match.missing.join(', ')}
          </p>
        )}
      </div>
    </Link>
  )
}

function ResultsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true" data-testid="results-skeleton">
      {[0, 1, 2, 3, 4, 5].map((row) => (
        <div key={row} className="rounded-3xl bg-cream/10 px-5 py-4">
          <div className="h-4 w-2/5 animate-pulse rounded-full bg-cream/20" />
          <div className="mt-2 h-3 w-1/4 animate-pulse rounded-full bg-cream/15" />
        </div>
      ))}
    </div>
  )
}
