"""Import tests (spec 10.5). Fixtures stand in for TheMealDB; nothing hits the network."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Ingredient, Recipe, RecipeIngredient
from scripts.import_mealdb import (
    ImportSummary,
    dedupe_lines,
    import_recipes,
    parse_meal,
    split_steps,
)

CATALOG_NAMES = ["Egg", "Rice", "Garlic", "Olive Oil", "Salt"]


def meal_fixture(**overrides: Any) -> dict[str, Any]:
    """A meal shaped like TheMealDB's: 20 ingredient slots, most of them empty."""
    meal: dict[str, Any] = {
        "idMeal": "52001",
        "strMeal": "Egg Fried Rice",
        "strCategory": "Rice",
        "strArea": "Chinese",
        "strMealThumb": "https://example.test/egg-fried-rice.jpg",
        "strYoutube": "",
        "strSource": "https://example.test/recipe",
        "strInstructions": "STEP 1 Boil the rice.\r\n\r\nFry the eggs.\r\nCombine and serve.",
        "strIngredient1": "Rice",
        "strMeasure1": "2 cups",
        "strIngredient2": "Eggs",
        "strMeasure2": "3",
        "strIngredient3": "Garlic Cloves",
        "strMeasure3": "2",
        "strIngredient4": "Salt",
        "strMeasure4": " ",
    }
    for slot in range(5, 21):
        meal[f"strIngredient{slot}"] = ""
        meal[f"strMeasure{slot}"] = ""
    meal.update(overrides)
    return meal


def test_split_steps_drops_blanks_and_step_prefixes() -> None:
    assert split_steps("STEP 1 Boil.\r\n\r\nSTEP 2 Fry.\r\nServe.") == ["Boil.", "Fry.", "Serve."]
    assert split_steps("") == []
    assert split_steps(None) == []


def test_parse_meal_pairs_ingredients_with_measures() -> None:
    parsed = parse_meal(meal_fixture())

    assert parsed.source_id == "52001"
    assert parsed.title == "Egg Fried Rice"
    assert parsed.area == "Chinese"
    # Empty strings become None rather than "".
    assert parsed.youtube_url is None
    assert parsed.steps == ["Boil the rice.", "Fry the eggs.", "Combine and serve."]
    # Names are canonical: "Eggs" -> egg, "Garlic Cloves" -> garlic (via the alias list).
    assert [(line.name, line.measure) for line in parsed.lines] == [
        ("rice", "2 cups"),
        ("egg", "3"),
        ("garlic", "2"),
        ("salt", None),
    ]


def test_parse_meal_ignores_empty_slots() -> None:
    parsed = parse_meal(meal_fixture(strIngredient2="   ", strMeasure2="1 tbsp"))

    assert [line.name for line in parsed.lines] == ["rice", "garlic", "salt"]


def test_duplicate_lines_merge_keeping_first_position() -> None:
    parsed = parse_meal(
        meal_fixture(strIngredient5="Egg", strMeasure5="1 extra", strIngredient2="Eggs")
    )

    egg_lines = [line for line in parsed.lines if line.name == "egg"]
    assert len(egg_lines) == 1
    assert egg_lines[0].measure == "3 + 1 extra"
    assert [line.name for line in parsed.lines].index("egg") == 1


def test_dedupe_keeps_a_measure_when_the_duplicate_has_none() -> None:
    lines = parse_meal(meal_fixture(strIngredient5="Eggs", strMeasure5="")).lines
    assert [line.measure for line in lines if line.name == "egg"] == ["3"]
    assert dedupe_lines(lines) == lines


def test_import_writes_recipe_ingredients_in_order(session: Session) -> None:
    summary = import_recipes(session, [parse_meal(meal_fixture())], CATALOG_NAMES)

    assert summary.recipes == 1
    assert summary.unmapped == []
    recipe = session.scalar(select(Recipe).where(Recipe.source_id == "52001"))
    assert recipe is not None
    assert recipe.steps == ["Boil the rice.", "Fry the eggs.", "Combine and serve."]

    rows = session.scalars(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.position)
    ).all()
    names = [session.get(Ingredient, row.ingredient_id).name for row in rows]
    assert names == ["rice", "egg", "garlic", "salt"]
    assert [row.position for row in rows] == [0, 1, 2, 3]


def test_importing_twice_changes_nothing(session: Session) -> None:
    parsed = [parse_meal(meal_fixture())]
    import_recipes(session, parsed, CATALOG_NAMES)
    counts_after_first = (
        session.scalar(select(func.count()).select_from(Recipe)),
        session.scalar(select(func.count()).select_from(Ingredient)),
        session.scalar(select(func.count()).select_from(RecipeIngredient)),
    )

    import_recipes(session, [parse_meal(meal_fixture())], CATALOG_NAMES)

    assert counts_after_first == (
        session.scalar(select(func.count()).select_from(Recipe)),
        session.scalar(select(func.count()).select_from(Ingredient)),
        session.scalar(select(func.count()).select_from(RecipeIngredient)),
    )


def test_unknown_ingredients_are_created_and_reported(session: Session) -> None:
    meal = meal_fixture(strIngredient5="Leftover Curry", strMeasure5="1 bowl")
    summary = ImportSummary()

    import_recipes(session, [parse_meal(meal)], CATALOG_NAMES, summary)

    created = session.scalar(select(Ingredient).where(Ingredient.name == "leftover curry"))
    assert created is not None
    assert created.display_name == "Leftover Curry"
    assert summary.unmapped == [("Leftover Curry", "leftover curry", "Egg Fried Rice")]


def test_reimport_replaces_changed_ingredient_lines(session: Session) -> None:
    import_recipes(session, [parse_meal(meal_fixture())], CATALOG_NAMES)
    # The same recipe, now without garlic and with a new title.
    changed = meal_fixture(strIngredient3="", strMeasure3="", strMeal="Egg Fried Rice v2")

    import_recipes(session, [parse_meal(changed)], CATALOG_NAMES)

    recipe = session.scalar(select(Recipe).where(Recipe.source_id == "52001"))
    assert recipe is not None
    assert recipe.title == "Egg Fried Rice v2"
    rows = session.scalars(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).all()
    names = {session.get(Ingredient, row.ingredient_id).name for row in rows}
    assert names == {"rice", "egg", "salt"}
