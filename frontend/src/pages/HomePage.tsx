/** Home: the pantry on the left, results on the right (spec section 6). */

import { PantryEditor } from '../components/PantryEditor'

export function HomePage() {
  return (
    <div className="grid grid-cols-[minmax(340px,420px)_1fr] gap-8">
      <PantryEditor />
      <section className="rounded-card bg-forest p-7 text-cream">
        <h2 className="mb-4 text-2xl font-bold tracking-tight">What you can make</h2>
        <p className="text-sm text-cream/80">Ranked results arrive in the next milestone.</p>
      </section>
    </div>
  )
}
