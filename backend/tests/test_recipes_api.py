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
    """Water is assumed, so Boiled egg counts 2 of 3 and outranks Egg fried rice."""
    fill_pantry(session, catalog, "egg", "rice", "garlic")

    response = client.get("/matches")

    assert response.status_code == 200
    body = response.json()
    assert [(row["title"], row["have"], row["total"], row["match"]) for row in body] == [
        ("Boiled egg", 2, 3, 67),
        ("Egg fried rice", 3, 7, 43),
    ]
    assert body[0]["missing"] == ["Salt"]
    assert body[1]["missing"] == ["Oil", "Salt", "Soy Sauce", "Spring Onion"]


def test_assumed_water_never_creates_matches_on_its_own(
    client: TestClient, fixture_recipes: dict[str, int]
) -> None:
    """An empty pantry stays empty: "anything that needs only water" is not an answer."""
    assert client.get("/matches").json() == []


def test_matches_is_empty_for_an_empty_pantry(
    client: TestClient, fixture_recipes: dict[str, int]
) -> None:
    assert client.get("/matches").json() == []


def test_matches_limit_is_validated(
    client: TestClient, session: Session, catalog: dict[str, int], fixture_recipes: dict[str, int]
) -> None:
    fill_pantry(session, catalog, "egg")

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
    # Ingredients come back in recipe order, not alphabetically.
    # Water is owned without being in the pantry, because it is assumed (spec section 4).
    assert [(i["display_name"], i["owned"]) for i in body["ingredients"]] == [
        ("Egg", True),
        ("Water", True),
        ("Salt", False),
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
