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

MATCH_QUERY = text("""
WITH scored AS (
  SELECT r.id, r.title, r.image_url,
         count(*) FILTER (WHERE ri.ingredient_id = ANY(:have))           AS have,
         count(*)                                                        AS total,
         array_agg(i.display_name ORDER BY ri.position)
           FILTER (WHERE ri.ingredient_id <> ALL(:have))                 AS missing
  FROM recipes r
  JOIN recipe_ingredients ri ON ri.recipe_id = r.id
  JOIN ingredients i         ON i.id = ri.ingredient_id
  -- The imported catalog is shared; a generated recipe is visible only to its owner (F8).
  WHERE r.source <> 'generated' OR r.created_by = :user_id
  GROUP BY r.id, r.title, r.image_url
)
SELECT id, title, image_url AS thumbnail_url, have, total,
       round(100.0 * have / total)::int AS match,
       coalesce(missing, '{}')          AS missing
FROM scored
WHERE have > 0
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


def find_matches(
    session: Session,
    ingredient_ids: Sequence[int],
    user_id: str,
    limit: int = 20,
) -> list[Match]:
    """Rank recipes by how much of each the user can already make.

    A pure function of its arguments: no HTTP, no auth, no request state, so it can be
    tested directly. An empty pantry matches nothing, and never reaches the database.
    """
    if not ingredient_ids:
        return []

    rows = session.execute(
        MATCH_QUERY,
        {"have": list(ingredient_ids), "user_id": user_id, "limit": limit},
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
        )
        for row in rows
    ]
