"""Ingredient-name normalization (spec 10.5, step 3).

Recipe lines and user input both arrive spelled inconsistently: "Eggs", "egg",
"2 large EGGS". Everything is reduced to one canonical form so that a pantry item
and a recipe line can point at the same `ingredients` row, which is what makes
matching a simple overlap count.

Normalization is: strip accents, lowercase, drop punctuation, collapse spaces,
singularize the last word, then apply the alias list.
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import inflect

ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "aliases.json"

# Words `inflect` singularizes wrongly, found by running it over TheMealDB's full
# ingredient list: it treats a trailing "s" as a plural marker even when it isn't
# ("asparagus" -> "asparagu"). Add to this list when the import report flags a name.
SINGULAR_EXCEPTIONS = frozenset(
    {
        "asparagus",
        "bass",
        "couscous",
        "cress",
        "frais",
        "hummus",
        "kabanos",
        "khus",
        "lemongrass",
        "molasses",
        "pois",
        "watercress",
    }
)

_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")


@lru_cache
def _inflect_engine() -> inflect.engine:
    return inflect.engine()


@lru_cache
def load_aliases() -> dict[str, str]:
    """Load data/aliases.json: {alias -> canonical name}, both already normalized."""
    if not ALIASES_PATH.exists():
        return {}
    with ALIASES_PATH.open(encoding="utf-8") as f:
        return {str(k): str(v) for k, v in json.load(f).items()}


def strip_accents(text: str) -> str:
    """ "Tequeños" -> "Tequenos", so accented spellings don't split an ingredient in two."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def singularize(word: str) -> str:
    """Singularize one word, leaving the known exceptions alone."""
    if word in SINGULAR_EXCEPTIONS:
        return word
    singular = _inflect_engine().singular_noun(word)
    # singular_noun returns False when the word is already singular.
    return singular if isinstance(singular, str) else word


def normalize(name: str) -> str:
    """Reduce a raw ingredient name to its canonical form.

    >>> normalize("2 Large Eggs")
    '2 large egg'
    >>> normalize("Garlic Cloves")
    'garlic'
    """
    cleaned = _PUNCTUATION.sub(" ", strip_accents(name).lower())
    words = _WHITESPACE.sub(" ", cleaned).strip().split(" ")
    if words == [""]:
        return ""

    words[-1] = singularize(words[-1])
    normalized = " ".join(words)
    return load_aliases().get(normalized, normalized)
