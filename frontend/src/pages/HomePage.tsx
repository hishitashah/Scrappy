/** Home: the pantry on the left, ranked results on the right (spec section 6). */

import { PantryEditor } from '../components/PantryEditor'
import { ResultsList } from '../components/ResultsList'

export function HomePage() {
  return (
    <div className="grid grid-cols-[minmax(340px,420px)_1fr] items-start gap-8">
      <PantryEditor />
      <ResultsList />
    </div>
  )
}
