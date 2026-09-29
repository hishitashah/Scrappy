/**
 * Top-level crash screen (spec 10.9).
 *
 * A render error anywhere below this unmounts the whole React tree, which would otherwise
 * leave a blank white page with no explanation. React only supports class components for
 * this; there is no hook equivalent.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keeps the detail in the browser console for debugging; the user sees the panel below.
    console.error('Scrappy crashed:', error, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-cream p-10">
        <div className="rounded-card max-w-md bg-forest p-9 text-cream">
          <h1 className="font-display mb-3 text-3xl font-bold tracking-tight">
            Something went wrong
          </h1>
          <p className="mb-6 text-cream/85">
            Scrappy hit an unexpected error. Reloading usually fixes it — your pantry is saved.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-full bg-cream px-6 py-2.5 font-medium text-forest-dark"
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}
