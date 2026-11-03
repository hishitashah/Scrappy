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
    """Egg + water + rice + garlic: Boiled egg qualifies at 67%, Egg fried rice does not."""
    matches = find_matches(session, pantry(catalog, "egg", "water", "rice", "garlic"), TEST_USER_ID)

    assert [(m.title, m.have, m.total, m.match) for m in matches] == [("Boiled egg", 2, 3, 67)]
    assert matches[0].missing == ["Salt"]


def test_ranking_without_the_floor(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """min_match=0 shows the raw ranking: percentage, then have, then title."""
    matches = find_matches(
        session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID, min_match=0
    )

    assert [(m.title, m.have, m.total, m.match) for m in matches] == [
        ("Egg fried rice", 3, 7, 43),
        ("Boiled egg", 1, 3, 33),
    ]
    assert matches[0].missing == ["Oil", "Salt", "Soy Sauce", "Spring Onion"]
    assert matches[1].missing == ["Water", "Salt"]


def test_recipes_below_the_floor_are_hidden(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """Under half the ingredients is a shopping list, not a suggestion (spec 10.2)."""
    have = pantry(catalog, "egg", "rice", "garlic")

    assert find_matches(session, have, TEST_USER_ID) == []
    assert len(find_matches(session, have, TEST_USER_ID, min_match=0)) == 2


def test_recipes_with_no_overlap_are_excluded(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    matches = find_matches(
        session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID, min_match=0
    )

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
    matches = find_matches(
        session, pantry(catalog, "egg", "rice", "garlic"), TEST_USER_ID, limit=1, min_match=0
    )

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

    matches = find_matches(session, pantry(catalog, "egg"), TEST_USER_ID, min_match=0)

    boiled_egg = next(match for match in matches if match.title == "Boiled egg")
    assert boiled_egg.have == 1


def test_find_matches_itself_assumes_nothing(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """The matching query is pure: the endpoint adds assumed staples, not this function."""
    matches = find_matches(session, pantry(catalog, "egg"), TEST_USER_ID, min_match=0)

    boiled_egg = next(match for match in matches if match.title == "Boiled egg")
    assert (boiled_egg.have, boiled_egg.total) == (1, 3)
    assert boiled_egg.missing == ["Water", "Salt"]


def test_assumed_staples_raise_the_score(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """Water counts toward Boiled egg's score without being in the pantry."""
    matches = find_matches(
        session, pantry(catalog, "egg"), TEST_USER_ID, staple_ids=[catalog["water"]]
    )

    boiled_egg = next(match for match in matches if match.title == "Boiled egg")
    assert (boiled_egg.have, boiled_egg.total, boiled_egg.match) == (2, 3, 67)
    assert boiled_egg.missing == ["Salt"]


def test_assumed_staples_never_qualify_a_recipe_alone(
    session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """A pantry of rice must not surface Boiled egg just because water is assumed."""
    matches = find_matches(
        session, pantry(catalog, "rice"), TEST_USER_ID, staple_ids=[catalog["water"]], min_match=0
    )

    assert "Boiled egg" not in {match.title for match in matches}
    assert "Egg fried rice" in {match.title for match in matches}


# --- Meals and sides (spec 10.2) -------------------------------------------------------
#
# A pantry can be dinner-capable and still return nothing but sides, because the 50% floor
# favours short recipes and short recipes are sides. `is_meal` is what lets the results
# list say so. The rule is a lookup on the imported category, not a judgment.


def categorised(session: Session, catalog: dict[str, int], title: str, category: str | None) -> int:
    """A one-ingredient recipe in the given category, so it matches a pantry of garlic."""
    recipe = Recipe(
        source="themealdb",
        source_id=f"cat-{title}",
        title=title,
        category=category,
        steps=["Cook."],
    )
    session.add(recipe)
    session.flush()
    session.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=catalog["garlic"], measure="1", position=0
        )
    )
    session.flush()
    return recipe.id


def test_a_main_course_is_a_meal(session: Session, catalog: dict[str, int]) -> None:
    categorised(session, catalog, "Garlic Chicken", "Chicken")

    matches = find_matches(session, pantry(catalog, "garlic"), TEST_USER_ID)

    assert [(m.title, m.is_meal) for m in matches] == [("Garlic Chicken", True)]


def test_sides_starters_and_desserts_are_not_meals(
    session: Session, catalog: dict[str, int]
) -> None:
    """The whole deny-list, so adding a fourth category can't pass unnoticed."""
    for title, category in (
        ("Garlic Bread", "Side"),
        ("Garlic Dip", "Starter"),
        ("Garlic Ice Cream", "Dessert"),
    ):
        categorised(session, catalog, title, category)

    matches = find_matches(session, pantry(catalog, "garlic"), TEST_USER_ID)

    assert {m.title for m in matches} == {"Garlic Bread", "Garlic Dip", "Garlic Ice Cream"}
    assert all(m.is_meal is False for m in matches)


def test_an_unknown_category_counts_as_a_meal(session: Session, catalog: dict[str, int]) -> None:
    """A deny-list, not an allow-list: a category TheMealDB adds later is dinner.

    The alternative is worse — a new upstream category would silently disappear out of the
    meals group, which is the one place the cook is looking for something to cook.
    """
    categorised(session, catalog, "Garlic Something", "Category We Have Never Seen")

    matches = find_matches(session, pantry(catalog, "garlic"), TEST_USER_ID)

    assert [(m.title, m.is_meal) for m in matches] == [("Garlic Something", True)]


def test_a_recipe_with_no_category_is_a_meal(session: Session, catalog: dict[str, int]) -> None:
    """Which is every generated recipe (F8): it has no category and invents none.

    It matters because generating is what the cook is offered when no meal matched. A
    generated recipe filed under sides would leave the meals group empty forever, still
    offering to generate the recipe that was just generated.
    """
    categorised(session, catalog, "Uncategorised Garlic", None)

    matches = find_matches(session, pantry(catalog, "garlic"), TEST_USER_ID)

    assert [(m.title, m.is_meal) for m in matches] == [("Uncategorised Garlic", True)]


def test_a_generated_recipe_is_a_meal(session: Session, catalog: dict[str, int]) -> None:
    """The real F8 shape: source 'generated', owned by the caller, no category."""
    session.add(User(id=TEST_USER_ID))
    session.flush()
    recipe = Recipe(
        source="generated",
        source_id=None,
        title="Garlic Rice Bowl",
        steps=["Cook."],
        created_by=TEST_USER_ID,
    )
    session.add(recipe)
    session.flush()
    session.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=catalog["garlic"], measure="1", position=0
        )
    )
    session.flush()

    matches = find_matches(session, pantry(catalog, "garlic"), TEST_USER_ID)

    assert [(m.title, m.generated, m.is_meal) for m in matches] == [
        ("Garlic Rice Bowl", True, True)
    ]
