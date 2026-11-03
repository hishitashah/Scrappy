"""Recipe matching (spec 10.2).

One SQL query does the whole job: count how many of each recipe's ingredients the user
has, count the total, and collect the names of the rest. Because all three come from the
same query, `total - have == len(missing)` always holds.

This is deliberately not AI: ingredient overlap is set math, so it is fast, free,
deterministic, and explainable. Don't reimplement it in Python or the frontend.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.categories import NON_MEAL_CATEGORIES

# Below this, a "match" is really a shopping list, so it isn't shown at all (spec 10.2).
MIN_MATCH_PERCENT = 50

MATCH_QUERY = text("""
WITH scored AS (
  SELECT r.id, r.title, r.image_url,
         r.source = 'generated'                                          AS generated,
         -- A null category is a generated recipe, which is a meal (see app/categories.py).
         (r.category IS NULL OR r.category <> ALL(:non_meals))            AS is_meal,
         count(*) FILTER (WHERE ri.ingredient_id = ANY(:have))           AS have,
         -- Ingredients the user actually put in their pantry, ignoring assumed staples.
         count(*) FILTER (WHERE ri.ingredient_id = ANY(:pantry))         AS from_pantry,
         count(*)                                                        AS total,
         array_agg(i.display_name ORDER BY ri.position)
           FILTER (WHERE ri.ingredient_id <> ALL(:have))                 AS missing
  FROM recipes r
  JOIN recipe_ingredients ri ON ri.recipe_id = r.id
  JOIN ingredients i         ON i.id = ri.ingredient_id
  -- The imported catalog is shared; a generated recipe is visible only to its owner (F8).
  WHERE r.source <> 'generated' OR r.created_by = :user_id
  GROUP BY r.id, r.title, r.image_url, r.source, r.category
)
SELECT id, title, image_url AS thumbnail_url, have, total,
       round(100.0 * have / total)::int AS match,
       coalesce(missing, '{}')          AS missing,
       generated, is_meal
FROM scored
-- An assumed staple raises a recipe's score but never qualifies it on its own: water
-- appears in 150 recipes, and listing all of them for an unrelated pantry is noise.
WHERE from_pantry > 0
  -- The floor hides the imported catalog's 600 recipes this cook can't make. A recipe
  -- written for this cook is not one of those, and may legitimately score low: F8 seasons
  -- from a few staples they may not own (spec 10.12). Filtering it out would mean
  -- generating a recipe, being shown it, going back, and finding it gone.
  AND (generated OR 100.0 * have / total >= :min_match)
ORDER BY match DESC, have DESC, title ASC
LIMIT :limit
""")


@dataclass(frozen=True)
class Match:
    """One ranked recipe. `match` is a whole-number percentage."""

    id: int
    title: str
    thumbnail_url: str | None
    have: int
    total: int
    match: int
    missing: list[str]
    # True for one of this user's own AI-written recipes (F8), which the card labels.
    generated: bool
    # False for a side, starter or dessert, which the results list groups separately so a
    # cook who wants dinner can see that none matched (spec 10.2).
    is_meal: bool


def find_matches(
    session: Session,
    ingredient_ids: Sequence[int],
    user_id: str,
    limit: int = 20,
    staple_ids: Sequence[int] = (),
    min_match: int = MIN_MATCH_PERCENT,
) -> list[Match]:
    """Rank recipes by how much of each the user can already make.

    `ingredient_ids` is the real pantry; `staple_ids` are assumed staples (spec section 4),
    which count toward a recipe's score but never qualify a recipe by themselves.
    `min_match` drops recipes the user is too far from making; pass 0 to rank everything.
    It never drops one of this user's own generated recipes, which are written for them
    and so are never "too far" — see the query's own comment.

    A pure function of its arguments: no HTTP, no auth, no request state, so it can be
    tested directly. An empty pantry matches nothing, and never reaches the database.
    """
    if not ingredient_ids:
        return []

    pantry = list(ingredient_ids)
    rows = session.execute(
        MATCH_QUERY,
        {
            "have": sorted({*pantry, *staple_ids}),
            "pantry": pantry,
            "user_id": user_id,
            "min_match": min_match,
            "limit": limit,
            "non_meals": list(NON_MEAL_CATEGORIES),
        },
    ).all()
    return [
        Match(
            id=row.id,
            title=row.title,
            thumbnail_url=row.thumbnail_url,
            have=row.have,
            total=row.total,
            match=row.match,
            missing=list(row.missing),
            generated=row.generated,
            is_meal=row.is_meal,
        )
        for row in rows
    ]
