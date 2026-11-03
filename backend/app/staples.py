"""Ingredients every kitchen is assumed to have (spec section 4).

Water, salt, pepper, cooking oil and butter. Each is cheap, keeps, and is in almost every
kitchen, so making the user type it adds nothing — and between them they appear in a large
share of the catalog, which is the point. A chicken-and-rice recipe listing chicken, rice,
water, salt, pepper, oil, onion, garlic and stock scored 22% for a cook holding chicken and
rice, and was hidden by the 50% floor. With these assumed it scores 67% and is offered.

**Perishables are deliberately not here.** Onion and garlic are the next most common
ingredients in the catalog, and assuming them would lift scores further — but a cook may
genuinely not have an onion tonight, and the app's one promise is that a recipe it offers
is a recipe they can cook. Being wrong in that direction costs more than a hidden recipe.

The names are canonical (`app/normalize.py`), and chosen against the real catalog rather
than guessed, because the near-misses are brutal: `salt cod` is a fish, `peanut butter`
and `butternut squash` are not butter, and `red pepper` and `green pepper` are bell
peppers — produce, not seasoning. `rose water` and `orange blossom water` are likewise
nothing to do with the tap.

Specialist oils are excluded for the same reason: sesame, peanut and coconut oil are
flavours a recipe is built around, not something to be assumed into a kitchen.

Assumed staples supplement a pantry; they never create one. A user with an empty pantry
still matches nothing, because "you can make anything that only needs salt" is not a
useful answer — see the `from_pantry > 0` guard in `app/matching.py`.

Mirrored in the frontend's `ingredientFilter.ts`, which hides these from autocomplete
since they always count already. `tests/test_staples.py` holds the two lists together.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient

ASSUMED_STAPLE_NAMES = frozenset(
    {
        # Out of a tap. Not rose water, orange blossom water or water chestnut.
        "water",
        # Not salt cod, and not celery salt, which is a spice blend.
        "salt",
        "kosher salt",
        "sea salt",
        # TheMealDB writes a bare "Pepper" for the seasoning. Bell peppers are produce and
        # are excluded, as is cayenne, which is a chilli rather than a seasoning everyone has.
        "pepper",
        "black pepper",
        # Everyday cooking oils, which stand in for one another. A recipe asking for
        # vegetable oil is satisfied by the olive oil already on the counter.
        "oil",
        "olive oil",
        "vegetable oil",
        "sunflower oil",
        "rapeseed oil",
        "canola oil",
        # Not peanut butter, butter beans, butternut squash or buttermilk.
        "butter",
        "unsalted butter",
        "salted butter",
    }
)


def staple_ingredient_ids(session: Session) -> list[int]:
    """Catalog ids of the assumed staples, or [] if the catalog hasn't been imported."""
    return list(
        session.scalars(
            select(Ingredient.id).where(Ingredient.name.in_(ASSUMED_STAPLE_NAMES))
        ).all()
    )
