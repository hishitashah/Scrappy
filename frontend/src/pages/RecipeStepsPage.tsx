/** `/recipes/:id/steps` — the numbered steps, and the end of the flow (spec 10.3). */

import { useParams } from 'react-router'

import { useRecipe } from '../api/hooks'
import { RecipePageFrame } from '../components/RecipePageFrame'

export function RecipeStepsPage() {
  const { id } = useParams()
  const recipeId = Number(id)
  const query = useRecipe(recipeId)

  return (
    <RecipePageFrame
      heading="Step by step instructions"
      query={query}
      previous={{ to: `/recipes/${recipeId}/ingredients`, label: 'Ingredients' }}
    >
      {(recipe) => (
        <>
          <ol className="flex list-decimal flex-col gap-3 pl-5 marker:font-semibold">
            {recipe.steps.map((step, index) => (
              <li key={`${index}-${step.slice(0, 16)}`}>{step}</li>
            ))}
          </ol>

          {(recipe.youtube_url ?? recipe.source_url) && (
            <div className="mt-6 flex flex-wrap gap-3 border-t border-cream/20 pt-5">
              {recipe.youtube_url && <ExternalLink href={recipe.youtube_url}>Watch video</ExternalLink>}
              {recipe.source_url && <ExternalLink href={recipe.source_url}>Original recipe</ExternalLink>}
            </div>
          )}
        </>
      )}
    </RecipePageFrame>
  )
}

function ExternalLink({ href, children }: { href: string; children: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="rounded-full bg-cream/15 px-4 py-1.5 text-sm font-medium hover:bg-cream/25"
    >
      {children} ↗
    </a>
  )
}
