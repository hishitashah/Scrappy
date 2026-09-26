"""Normalization tests (spec 10.5): table-driven, including the inflect exceptions."""

import pytest

from app.normalize import SINGULAR_EXCEPTIONS, load_aliases, normalize, singularize

# (raw name, expected canonical form)
CASES = [
    # Case, spacing, and punctuation
    ("Egg", "egg"),
    ("EGG", "egg"),
    ("  Bay   Leaves  ", "bay leaf"),
    ("Chicken-Breast", "chicken breast"),
    ("Creme Fraiche!", "creme fraiche"),
    ("", ""),
    ("   ", ""),
    # Plurals: only the last word is singularized
    ("Eggs", "egg"),
    ("Tomatoes", "tomato"),
    ("Potatoes", "potato"),
    ("Anchovies", "anchovy"),
    ("Spring Onions", "spring onion"),
    ("Chicken Thighs", "chicken thigh"),
    ("Olives", "olive"),
    # Words inflect would mangle without the exceptions list
    ("Asparagus", "asparagus"),
    ("Couscous", "couscous"),
    ("Hummus", "hummus"),
    ("Molasses", "molasses"),
    ("Lemongrass", "lemongrass"),
    ("Sea Bass", "sea bass"),
    ("Petit Pois", "petit pois"),
    ("Watercress", "watercress"),
    # Accents are stripped, so one spelling can't split an ingredient in two
    ("Tequeños", "tequeno"),
    ("Jalapeño", "jalapeno"),
    # Already canonical: normalizing is idempotent
    ("garlic", "garlic"),
    ("olive oil", "olive oil"),
    # Aliases are applied last
    ("Garlic Cloves", "garlic"),
    ("Minced Garlic", "garlic"),
    ("Corn Flour", "cornflour"),
    ("Whole Milk", "milk"),
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize_is_idempotent(raw: str, expected: str) -> None:
    """Normalizing an already-normalized name must not change it again."""
    assert normalize(normalize(raw)) == expected


def test_singularize_leaves_exceptions_untouched() -> None:
    for word in SINGULAR_EXCEPTIONS:
        assert singularize(word) == word


def test_aliases_are_stored_in_normalized_form() -> None:
    """Both sides of every alias must already be canonical, or lookups would miss."""
    for alias, target in load_aliases().items():
        assert normalize(alias) == target, f"alias {alias!r} does not resolve to {target!r}"
        assert normalize(target) == target, f"alias target {target!r} is not canonical"
