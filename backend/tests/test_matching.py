"""Matching tests (spec 10.2), including the worked example the spec fixes exactly."""

from sqlalchemy.orm import Session

from app.matching import find_matches
from app.models import PantryItem, Recipe, RecipeIngredient, User
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


def pantry(catalog: dict[str, int], *names: str) -> list[int]:
    return [catalog[name] for name in names]


def test_worked_example_from_the_spec(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """Egg + rice + garlic returns exactly these two rows, in this order."""
    matches = find_matches(session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID)

    assert [(m.title, m.have, m.total, m.match) for m in matches] == [
        ("Egg fried rice", 3, 7, 43),
        ("Boiled egg", 1, 3, 33),
    ]
    assert matches[0].missing == ["Oil", "Salt", "Soy Sauce", "Spring Onion"]
    assert matches[1].missing == ["Water", "Salt"]


def test_recipes_with_no_overlap_are_excluded(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    matches = find_matches(session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID)

    titles = {match.title for match in matches}
    assert "Fried chicken" not in titles
    assert "Pancakes" not in titles


def test_missing_count_always_equals_total_minus_have(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    matches = find_matches(session, pantry(catalog, "egg", "rice", "garlic", "flour"), TEST_USER_ID)

    assert matches, "expected at least one match"
    for match in matches:
        assert match.total - match.have == len(match.missing)


def test_empty_pantry_returns_nothing(session: Session, fixture_recipes: dict[str, int]) -> None:
    assert find_matches(session, [], TEST_USER_ID) == []


def test_pantry_that_matches_no_recipe_returns_nothing(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    unused = [catalog["salt"] + 10_000]

    assert find_matches(session, unused, TEST_USER_ID) == []


def test_limit_caps_the_number_of_rows(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    matches = find_matches(session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID, limit=1)

    assert [match.title for match in matches] == ["Egg fried rice"]


def test_another_users_generated_recipe_is_invisible(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """A generated recipe belongs to one user; matching hides it from everyone else (F8)."""
    session.add(User(id=OTHER_USER_ID))
    session.flush()
    generated = Recipe(
        source="generated",
        source_id=None,
        title="Aaa generated egg dish",  # sorts first, so a leak would be obvious
        steps=["Cook."],
        created_by=OTHER_USER_ID,
    )
    session.add(generated)
    session.flush()
    session.add(RecipeIngredient(recipe_id=generated.id, ingredient_id=catalog["egg"], position=0))
    session.flush()

    mine = find_matches(session, pantry(catalog, "egg"), TEST_USER_ID)
    theirs = find_matches(session, pantry(catalog, "egg"), OTHER_USER_ID)

    assert "Aaa generated egg dish" not in {match.title for match in mine}
    assert "Aaa generated egg dish" in {match.title for match in theirs}


def test_own_generated_recipe_is_matched(
    session: Session, test_user: str, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    generated = Recipe(
        source="generated",
        source_id=None,
        title="My generated egg dish",
        steps=["Cook."],
        created_by=test_user,
    )
    session.add(generated)
    session.flush()
    session.add(RecipeIngredient(recipe_id=generated.id, ingredient_id=catalog["egg"], position=0))
    session.flush()

    matches = find_matches(session, pantry(catalog, "egg"), TEST_USER_ID)

    mine = next(match for match in matches if match.title == "My generated egg dish")
    assert (mine.have, mine.total, mine.match, mine.missing) == (1, 1, 100, [])


def test_pantry_items_of_other_users_do_not_affect_results(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    session.add(User(id=OTHER_USER_ID))
    session.flush()
    session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=catalog["salt"]))
    session.flush()

    matches = find_matches(session, pantry(catalog, "egg"), TEST_USER_ID)

    boiled_egg = next(match for match in matches if match.title == "Boiled egg")
    assert boiled_egg.have == 1
