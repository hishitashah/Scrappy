/**
 * The public front door (docs/landing page.png).
 *
 * Signed-out visitors land here rather than on a login form: a form asks for a commitment
 * before saying what the app does. "Get Started" is the only path onward, and it leads to
 * sign-in or sign-up.
 */

import { Link } from "react-router";

export function LandingPage() {
  return (
    <main className="min-h-screen bg-cream">
      <div className="mx-auto grid max-w-[1180px] grid-cols-[minmax(320px,0.9fr)_1fr] items-center gap-16 px-10 py-16">
        {/* The photo sits in a rounded frame with a forest block offset behind it. Both are
            CSS rather than part of the image, so they scale with the layout. */}
        <div className="relative">
          <div
            aria-hidden="true"
            className="absolute -bottom-8 -left-8 h-[85%] w-[85%] rounded-[2rem] bg-forest"
          />
          <img
            src="/landing-photo.jpg"
            alt="Someone grinding pepper over a bowl of salad"
            className="relative aspect-[560/774] w-full rounded-[2rem] object-cover"
          />
        </div>

        <div>
          {/* The hat sits on the S, sized in `em` so it scales with the wordmark instead
              of needing its own numbers at every size. */}
          <h1 className="font-wordmark pt-[0.45em] text-8xl leading-none font-normal tracking-tight">
            <span className="relative inline-block">
              S
              <img
                src="/chef-hat.png"
                alt=""
                aria-hidden="true"
                className="pointer-events-none absolute -top-[0.38em] left-1/2 w-[0.78em] -translate-x-1/2 -rotate-12 select-none"
              />
            </span>
            CRAPPY
          </h1>

          <p className="mt-6 max-w-lg text-lg leading-snug text-muted">
            Most recipe sites send you shopping. Scrappy starts with what you have.
          </p>

          <p className="mt-16 max-w-md text-2xl leading-snug text-ink">
            Instant meal generator with what you have available!
          </p>

          <div className="mt-8 flex items-center gap-4">
            <Link
              to="/login"
              className="rounded-full bg-forest px-10 py-4 text-xl font-medium text-cream transition hover:bg-forest-dark"
            >
              Get Started
            </Link>
            <Link
              to="/login"
              aria-hidden="true"
              tabIndex={-1}
              className="flex size-14 items-center justify-center rounded-full bg-forest text-cream transition hover:bg-forest-dark"
            >
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <path
                  d="M9 5l7 7-7 7"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
