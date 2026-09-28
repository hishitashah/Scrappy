import { Route, Routes } from 'react-router'

import { AppFrame } from './components/AppFrame'
import { HomePage } from './pages/HomePage'
import { RecipeIngredientsPage } from './pages/RecipeIngredientsPage'
import { RecipeIntroPage } from './pages/RecipeIntroPage'
import { RecipeStepsPage } from './pages/RecipeStepsPage'

export default function App() {
  return (
    <AppFrame>
      <Routes>
        <Route path="/" element={<HomePage />} />
        {/* One page per URL, so back, forward and refresh all behave (spec US-7). */}
        <Route path="/recipes/:id" element={<RecipeIntroPage />} />
        <Route path="/recipes/:id/ingredients" element={<RecipeIngredientsPage />} />
        <Route path="/recipes/:id/steps" element={<RecipeStepsPage />} />
      </Routes>
    </AppFrame>
  )
}
