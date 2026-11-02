/**
 * What AI content looks like, and what the three AI failures say (spec 10.11, 10.12).
 *
 * Shared by the substitutions panel (F7) and the generate button (F8), which fail in
 * exactly the same three ways and differ by one word. Having one copy also means one
 * decision about how a model's output is set apart from the recipe around it.
 */

import type { ReactNode } from 'react'

import { ApiError } from '../api/client'

/** The dashed frame every piece of AI output sits in, so none can pass for recipe text. */
export function AiNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl border border-dashed border-cream/30 bg-cream/10 p-4 text-sm text-cream/85">
      {children}
    </p>
  )
}

/**
 * The "AI-generated" mark, wherever a model wrote what is being shown.
 *
 * One component so the wording can't drift between the places it appears. `compact` is for
 * the results card, where it sits beside the match percentage rather than among the tags.
 */
export function AiBadge({ compact = false }: { compact?: boolean }) {
  const size = compact ? 'px-2 py-0.5 text-[0.625rem]' : 'px-3 py-1 text-xs'
  return (
    <span
      className={`shrink-0 rounded-full border border-dashed border-cream/40 bg-cream/10 font-semibold tracking-[0.08em] uppercase ${size}`}
    >
      AI-generated
    </span>
  )
}

/**
 * The three failures worth telling apart.
 *
 * A 503 is either the kill switch or the month's budget, and the user can't act on the
 * difference — "paused" is true either way, and next month is the right expectation for
 * the one that matters. Only the last case offers a retry, because the other two will give
 * the same answer however many times they are asked.
 *
 * Only the two messages that name what was being asked for differ between the features;
 * the 503 is about the feature as a whole, so it reads the same either way.
 */
export function AiProblem({
  error,
  dailyLimit,
  failed,
  onRetry,
}: {
  error: unknown
  /** Shown on a 429: what the user has used up today. */
  dailyLimit: string
  /** Shown on anything else, beside a retry: what couldn't be done. */
  failed: string
  onRetry: () => void
}) {
  const status = error instanceof ApiError ? error.status : 0

  if (status === 429) {
    return <AiNote>{dailyLimit}</AiNote>
  }
  if (status === 503) {
    return <AiNote>AI features are paused until next month.</AiNote>
  }

  return (
    <AiNote>
      <span className="mr-3">{failed}</span>
      <button type="button" onClick={onRetry} className="font-medium underline">
        Try again
      </button>
    </AiNote>
  )
}
