/**
 * The sign-in and sign-up page, reached from the landing page's "Get Started" (spec 10.4).
 *
 * Amplify's component brings sign-in, sign-up, the emailed verification code and password
 * reset, with their error states. Those paths are tedious and easy to get subtly wrong, so
 * the trade-off taken here is to style a working component rather than build three screens.
 */

import { Authenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css'
import { Link } from 'react-router'

import './authenticator-theme.css'

export function LoginScreen() {
  return (
    <div className="relative flex min-h-screen items-center justify-center bg-cream p-8">
      {/* Positioned rather than placed in the flow, so the card stays centred on the page
          exactly as it would without it. Decoration, so assistive tech skips it. */}
      <img
        src="/bear-chef.png"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute top-16 left-24 hidden w-[190px] select-none lg:block"
      />

      <Authenticator
        loginMechanisms={['email']}
        signUpAttributes={[]}
        components={{
          Header: () => (
            <header className="px-2 pt-8 pb-4 text-center">
              <Link to="/" className="font-brand text-6xl leading-none text-forest">
                Scrappy
              </Link>
              <p className="mt-3 text-sm text-muted">
                Quick meals from what you already have
              </p>
            </header>
          ),
        }}
      />
    </div>
  )
}
