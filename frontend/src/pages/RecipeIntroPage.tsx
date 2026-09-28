/** `/recipes/:id` — the photo beside the title card (spec 10.3). */

import { Link, useParams } from 'react-router'

import { useRecipe } from '../api/hooks'
import { RecipePageFrame } from '../components/RecipePageFrame'

export function RecipeIntroPage() {
  const { id } = useParams()
  const recipeId = Number(id)
  const query = useRecipe(recipeId)

  return (
    <div>
      <Link to="/" className="mb-5 inline-block text-sm font-medium text-muted hover:text-ink">
        ← Back to results
      </Link>

      <RecipePageFrame
        heading={query.data?.title ?? ''}
        query={query}
        next={{ to: `/recipes/${recipeId}/ingredients`, label: 'Ingredients' }}
      >
        {(recipe) => (
          <div className="flex flex-col gap-6">
            {recipe.image_url && (
              <img
                src={recipe.image_url}
                alt={recipe.title}
                className="aspect-[4/3] w-full rounded-3xl object-cover"
              />
            )}
            <div>
              <h3 className="font-display text-3xl font-bold tracking-tight">{recipe.title}</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {[recipe.category, recipe.area].filter(Boolean).map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-cream/15 px-3 py-1 text-sm font-medium"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </RecipePageFrame>
    </div>
  )
}
