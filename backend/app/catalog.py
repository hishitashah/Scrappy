"""Mapping free-text ingredient names onto catalog rows (spec 10.5, 10.11, 10.12).

A model writes "plain yogurt" and the catalog holds "yogurt"; a user types "Garlic Cloves"
and the catalog holds "garlic". Both reach the same row because both go through
`normalize`, and because an ingredient's `aliases` are searched alongside its name.

Two functions, differing only in what happens to a name nothing matches:

- `find_ingredient_ids` leaves it out. F7 asks "does the cook own this?", and a name with
  no catalog row is an answer of no, not a reason to invent an ingredient.
- `ensure_ingredient_ids` creates it. F8 is saving a recipe, and an ingredient that was
  dropped for being unrecognized would leave a step referring to nothing.
"""

from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Ingredient
from app.normalize import normalize


def find_ingredient_ids(session: Session, names: Sequence[str]) -> dict[str, int]:
    """Map each raw name to a catalog ingredient id, where one already exists.

    Keyed by the raw name as given, so the caller can look up what it asked about without
    normalizing a second time. Names that match nothing are simply absent.
    """
    wanted = {normalize(name): name for name in names}
    if not wanted:
        return {}

    rows = session.execute(
        select(Ingredient.id, Ingredient.name, Ingredient.aliases).where(
            or_(
                Ingredient.name.in_(wanted),
                Ingredient.aliases.overlap(list(wanted)),
            )
        )
    ).all()

    found: dict[str, int] = {}
    for row in rows:
        for key in (row.name, *row.aliases):
            if key in wanted:
                found[wanted[key]] = row.id
    return found


def ensure_ingredient_ids(session: Session, names: Sequence[str]) -> dict[str, int]:
    """Map every raw name to an ingredient id, creating the rows that don't exist yet.

    New rows are built exactly as the import builds them — `normalize` for the canonical
    name, the name as written for the label — so a generated recipe's ingredients behave
    like any others in matching and autocomplete. See `upsert_ingredients` in
    `scripts/import_mealdb.py`; the app can't import from `scripts/`, which is why the
    shared part lives here.

    A name the model invented therefore joins the catalog everyone's autocomplete reads.
    That is what spec 10.12 asks for, and it is survivable: suggestions are ranked by how
    many recipes use an ingredient, so a brand-new one sorts last behind everything real.

    Flushed one at a time so each row has its id, and because two names in the same recipe
    can normalize to the same ingredient ("Eggs" and "egg") — the second must find the
    first rather than insert a duplicate and trip the unique constraint on `name`.

    A name that normalizes to nothing is absent from the result, so callers must treat a
    missing key as a line to skip rather than assume every name came back.
    """
    found = find_ingredient_ids(session, names)

    for raw in names:
        if raw in found:
            continue
        canonical = normalize(raw)
        # Punctuation and whitespace normalize to nothing. An ingredient with no name is
        # not an ingredient, so it is left out of the result rather than inserted as a
        # nameless row the whole catalog would then carry. Callers skip what's absent.
        if not canonical:
            continue
        existing = session.scalar(select(Ingredient.id).where(Ingredient.name == canonical))
        if existing is None:
            ingredient = Ingredient(name=canonical, display_name=raw)
            session.add(ingredient)
            session.flush()
            existing = ingredient.id
        found[raw] = existing
    return found
