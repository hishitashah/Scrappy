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
