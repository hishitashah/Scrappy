"""API tests for /matches and /recipes/{id} (spec 10.2, 10.3)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PantryItem, Recipe, RecipeIngredient, User
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


def fill_pantry(session: Session, catalog: dict[str, int], *names: str) -> None:
    for name in names:
        session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog[name]))
    session.flush()


def test_matches_ranks_recipes(
    client: TestClient, session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """Staples are assumed, so both recipes clear the floor (spec section 4).

    Boiled egg is egg, water and salt, all of them owned or assumed: 3 of 3. Egg fried
    rice adds oil and salt to the three real pantry items, reaching 5 of 7 — it was hidden
    at 43% before staples were assumed, and it is the case that prompted assuming them.
    """
    fill_pantry(session, catalog, "egg", "rice", "garlic")

    response = client.get("/matches")

    assert response.status_code == 200
    body = response.json()
    assert [(row["title"], row["have"], row["total"], row["match"]) for row in body] == [
        ("Boiled egg", 3, 3, 100),
        ("Egg fried rice", 5, 7, 71),
    ]
    assert body[0]["missing"] == []
    assert body[1]["missing"] == ["Soy Sauce", "Spring Onion"]


def test_assumed_water_never_creates_matches_on_its_own(
    client: TestClient, fixture_recipes: dict[str, int]
) -> None:
    """An empty pantry stays empty: "anything that needs only water" is not an answer."""
    assert client.get("/matches").json() == []


def test_matches_is_empty_for_an_empty_pantry(
    client: TestClient, fixture_recipes: dict[str, int]
) -> None:
    assert client.get("/matches").json() == []


def test_matches_hides_recipes_below_the_floor(
    client: TestClient, session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    """Fried chicken is chicken, flour, oil, salt and pepper — three of them assumed.

    A pantry of flour alone therefore reaches 4 of 5 and clears the floor, where before
    staples it was 1 of 5. Boiled egg stays hidden: its only real ingredient is the egg,
    which this cook does not have, so the `from_pantry > 0` guard excludes it.
    """
    fill_pantry(session, catalog, "flour")

    rows = client.get("/matches").json()

    assert [(row["title"], row["have"], row["total"]) for row in rows] == [
        ("Pancakes", 1, 1),
        ("Fried chicken", 4, 5),
    ]


def test_matches_limit_is_validated(
    client: TestClient, session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    fill_pantry(session, catalog, "flour")

    assert len(client.get("/matches?limit=1").json()) == 1
    assert client.get("/matches?limit=0").status_code == 422
    assert client.get("/matches?limit=51").status_code == 422


def test_recipe_detail_marks_owned_ingredients(
    client: TestClient, session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    fill_pantry(session, catalog, "egg")

    response = client.get(f"/recipes/{fixture_recipes['Boiled egg']}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Boiled egg"
    assert body["steps"] == ["Cook."]
    # Ingredients come back in recipe order, not alphabetically. Water and salt are owned
    # without being in the pantry, because both are assumed staples (spec section 4) —
    # only the egg here is something the cook actually typed in.
    assert [(i["display_name"], i["owned"]) for i in body["ingredients"]] == [
        ("Egg", True),
        ("Water", True),
        ("Salt", True),
    ]
    assert body["ingredients"][0]["measure"] == "1"


def test_recipe_detail_returns_404_for_an_unknown_id(client: TestClient) -> None:
    response = client.get("/recipes/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Recipe not found"


def test_recipe_detail_hides_another_users_generated_recipe(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    session.add(User(id=OTHER_USER_ID))
    session.flush()
    generated = Recipe(
        source="generated",
        source_id=None,
        title="Their generated dish",
        steps=["Cook."],
        created_by=OTHER_USER_ID,
    )
    session.add(generated)
    session.flush()
    session.add(RecipeIngredient(recipe_id=generated.id, ingredient_id=catalog["egg"], position=0))
    session.flush()

    assert client.get(f"/recipes/{generated.id}").status_code == 404


def test_recipe_detail_shows_your_own_generated_recipe(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    generated = Recipe(
        source="generated",
        source_id=None,
        title="My generated dish",
        steps=["Cook."],
        created_by=TEST_USER_ID,
    )
    session.add(generated)
    session.flush()
    session.add(RecipeIngredient(recipe_id=generated.id, ingredient_id=catalog["egg"], position=0))
    session.flush()

    response = client.get(f"/recipes/{generated.id}")

    assert response.status_code == 200
    assert response.json()["title"] == "My generated dish"
