"""Assumed staples (spec section 4): water, salt, pepper, cooking oil and butter.

Two things are worth testing here and one of them is new. The list itself is a product
decision, so it is pinned rather than inferred — a name appearing or disappearing should
be a deliberate edit, not something that happens quietly.

The other is the mirror. `frontend/src/lib/ingredientFilter.ts` holds the same list so the
autocomplete can hide what already counts, and until the list had more than one entry
nothing checked that the two agreed. A name in the backend only is an ingredient the
matcher counts while the picker still offers it, so a cook adds salt and nothing changes.
A name in the frontend only is worse: the picker hides it and the matcher ignores it, so
the ingredient becomes unreachable.
"""

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.staples import ASSUMED_STAPLE_NAMES, staple_ingredient_ids

FILTER_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "ingredientFilter.ts"

# Matches each quoted name inside `export const ASSUMED_STAPLES = new Set([...])`.
_SET_BODY = re.compile(r"ASSUMED_STAPLES\s*=\s*new Set\(\[(.*?)\]\)", re.DOTALL)
_NAME = re.compile(r"'([^']+)'")


def test_the_assumed_staples_are_what_we_think_they_are() -> None:
    """Pinned deliberately: section 4 calls this a spec change, not a judgement call."""
    assert ASSUMED_STAPLE_NAMES == frozenset(
        {
            "water",
            "salt",
            "kosher salt",
            "sea salt",
            "pepper",
            "black pepper",
            "oil",
            "olive oil",
            "vegetable oil",
            "sunflower oil",
            "rapeseed oil",
            "canola oil",
            "butter",
            "unsalted butter",
            "salted butter",
        }
    )


def test_no_perishable_is_assumed() -> None:
    """The line the list is drawn on, named so that crossing it has to be deliberate.

    Onion and garlic are the catalog's two most common ingredients after salt, so they are
    the tempting ones. A cook may genuinely not have an onion, and a recipe offered as
    cookable has to be cookable.
    """
    for perishable in ("onion", "garlic", "egg", "milk", "tomato", "parsley"):
        assert perishable not in ASSUMED_STAPLE_NAMES


def test_the_near_misses_are_not_assumed() -> None:
    """Names a careless list would swallow. Each is a real catalog ingredient.

    `salt cod` is a fish, `peanut butter` and `butternut squash` are not butter, and red
    and green peppers are produce rather than seasoning.
    """
    for near_miss in (
        "salt cod",
        "celery salt",
        "peanut butter",
        "butter bean",
        "butternut squash",
        "buttermilk",
        "red pepper",
        "green pepper",
        "cayenne pepper",
        "sesame seed oil",
        "peanut oil",
        "coconut oil",
        "rose water",
        "water chestnut",
    ):
        assert near_miss not in ASSUMED_STAPLE_NAMES


def test_the_frontend_mirror_exists() -> None:
    """A missing file would make the comparison below vacuously true."""
    assert FILTER_TS.is_file(), f"expected the mirrored staple list at {FILTER_TS}"
    assert _SET_BODY.search(FILTER_TS.read_text(encoding="utf-8")), (
        "found no `ASSUMED_STAPLES = new Set([...])` — has the shape changed?"
    )


def test_the_two_staple_lists_hold_the_same_names() -> None:
    """The check `test_stores.py` noted this pair was missing."""
    body = _SET_BODY.search(FILTER_TS.read_text(encoding="utf-8"))
    assert body
    mirrored = set(_NAME.findall(body.group(1)))

    assert mirrored, "found no names — has the shape of ASSUMED_STAPLES changed?"
    assert mirrored == set(ASSUMED_STAPLE_NAMES)


def test_staple_ids_resolve_against_the_catalog(session: Session, catalog: dict[str, int]) -> None:
    """The fixture catalog holds water and salt; the rest of the list simply isn't in it."""
    assert sorted(staple_ingredient_ids(session)) == sorted([catalog["water"], catalog["salt"]])


def test_no_staples_before_the_catalog_is_imported(session: Session) -> None:
    assert staple_ingredient_ids(session) == []
