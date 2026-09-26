"""Ingredients every kitchen is assumed to have (spec section 4).

Water is the only one. It comes out of a tap, so making the user type it adds nothing,
and 150 of the catalog's recipes call for it. Everything else — salt, oil, flour — is a
real shopping decision, so it still has to be in the pantry to count.

Assumed staples supplement a pantry; they never create one. A user with an empty pantry
still matches nothing, because "you can make anything that only needs water" is not a
useful answer.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ingredient

ASSUMED_STAPLE_NAMES = frozenset({"water"})


def staple_ingredient_ids(session: Session) -> list[int]:
    """Catalog ids of the assumed staples, or [] if the catalog hasn't been imported."""
    return list(
        session.scalars(
            select(Ingredient.id).where(Ingredient.name.in_(ASSUMED_STAPLE_NAMES))
        ).all()
    )
