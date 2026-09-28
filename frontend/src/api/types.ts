/** Response shapes from the Scrappy API (spec section 11). */

export interface Ingredient {
  id: number
  name: string
  display_name: string
  aliases: string[]
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
  ingredients: RecipeIngredient[]
}
