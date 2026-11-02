/**
 * The three recipe pages' shared behaviour (spec 10.3): the loading, error and 404 states,
 * so all three behave identically, plus the circular chevrons that advance the flow.
 *
 * The frame itself — the heading and the forest card — is `PageShell`, shared with the
 * grocery list.
 */

import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../api/client'
import type { RecipeDetail } from '../api/types'
import { PageShell } from './PageShell'

/** A labelled destination: the arrows carry words, so "next" is never a guess. */
interface Step {
  to: string
  label: string
}

interface Props {
  heading: ReactNode
  query: {
    data: RecipeDetail | undefined
    isPending: boolean
    isError: boolean
    error: unknown
    refetch: () => void
  }
  children: (recipe: RecipeDetail) => ReactNode
  /** The previous page in the flow; omitted on the first one. */
  previous?: Step
  /** The next page; omitted on the last one, which offers "Back to results" instead. */
  next?: Step
}

export function RecipePageFrame({ heading, query, children, previous, next }: Props) {
  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <PageShell heading={notFound ? 'Recipe not found' : 'Something went wrong'}>
        <div className="text-cream/85">
          {notFound ? (
            <>
              <p className="mb-4">We couldn&apos;t find that recipe.</p>
              <CreamLink to="/">Back to results</CreamLink>
            </>
          ) : (
            <>
              <p className="mb-4">Couldn&apos;t load this recipe.</p>
              <button
                type="button"
                onClick={() => query.refetch()}
                className="rounded-full bg-cream px-5 py-2 font-medium text-forest-dark"
              >
                Try again
              </button>
            </>
          )}
        </div>
      </PageShell>
    )
  }

  if (query.isPending || !query.data) {
    return (
      <PageShell heading={heading}>
        <div className="flex flex-col gap-3" aria-hidden="true" data-testid="recipe-skeleton">
          {[0, 1, 2, 3, 4].map((row) => (
            <div key={row} className="h-4 animate-pulse rounded-full bg-cream/20" />
          ))}
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell
      heading={heading}
      footer={
        <>
          {previous ? <PreviousLink step={previous} /> : <span />}
          {next ? <NextLink step={next} /> : <BackToResults />}
        </>
      }
    >
      {children(query.data)}
    </PageShell>
  )
}

function NextLink({ step }: { step: Step }) {
  return (
    <Link
      to={step.to}
      className="flex items-center gap-3 rounded-full bg-forest py-2 pr-2 pl-5 font-medium text-cream transition hover:bg-forest-dark"
    >
      {step.label}
      <span className="flex size-9 items-center justify-center rounded-full bg-cream/15">
        <Chevron direction="right" />
      </span>
    </Link>
  )
}

function PreviousLink({ step }: { step: Step }) {
  return (
    <Link
      to={step.to}
      className="flex items-center gap-3 rounded-full border border-forest/30 py-2 pr-5 pl-2 font-medium text-forest transition hover:bg-forest-light"
    >
      <span className="flex size-9 items-center justify-center rounded-full bg-forest/10">
        <Chevron direction="left" />
      </span>
      {step.label}
    </Link>
  )
}

function Chevron({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={direction === 'right' ? 'M9 5l7 7-7 7' : 'M15 5l-7 7 7 7'}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BackToResults() {
  return (
    <Link
      to="/"
      className="rounded-full bg-forest px-6 py-3 font-medium text-cream transition hover:bg-forest-dark"
    >
      Back to results
    </Link>
  )
}

function CreamLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="rounded-full bg-cream px-5 py-2 font-medium text-forest-dark">
      {children}
    </Link>
  )
}
