/** Response shapes from the Scrappy API (spec section 11). */

export interface Ingredient {
  id: number
  name: string
  display_name: string
  aliases: string[]
  /** How many recipes use it; suggestions are ranked by this. */
  recipe_count: number
}

export interface PantryItem {
  ingredient_id: number
  display_name: string
  added_at: string
}

export interface Match {
  id: number
  title: string
  thumbnail_url: string | null
  have: number
  total: number
  match: number
  missing: string[]
  /** True for one of your own AI-written recipes (F8), which the card labels. */
  generated: boolean
}

export interface RecipeIngredient {
  id: number
  display_name: string
  measure: string | null
  owned: boolean
}

export interface RecipeDetail {
  id: number
  title: string
  category: string | null
  area: string | null
  image_url: string | null
  youtube_url: string | null
  source_url: string | null
  steps: string[]
  /** True for an AI-written recipe (F8): the page badges it in place of the tags. */
  generated: boolean
  ingredients: RecipeIngredient[]
}

/** One AI substitution (spec 10.11). `in_pantry` is computed by the API, not the model. */
export interface Substitution {
  missing_ingredient: string
  suggestion: string
  reason: string
  in_pantry: boolean
}

export interface SubstitutionsResponse {
  suggestions: Substitution[]
}
