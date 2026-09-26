"""API tests for /ingredients and /pantry (spec 10.1)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PantryItem, User
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


def add_items(client: TestClient, *ingredient_ids: int):
    return client.post("/pantry/items", json={"ingredient_ids": list(ingredient_ids)})


def give_other_user(session: Session, ingredient_id: int) -> None:
    """Put one ingredient in a second user's pantry, to prove the two never mix."""
    session.add(User(id=OTHER_USER_ID))
    session.flush()  # the user row must exist before its pantry row references it
    session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=ingredient_id))
    session.flush()


def test_list_ingredients_returns_the_catalog(client: TestClient, catalog: dict[str, int]) -> None:
    response = client.get("/ingredients")

    assert response.status_code == 200
    body = response.json()
    assert [item["display_name"] for item in body] == ["Egg", "Garlic", "Rice", "Salt", "Water"]
    egg = next(item for item in body if item["name"] == "egg")
    assert egg["aliases"] == ["eggs"]
    assert egg["id"] == catalog["egg"]


def test_list_ingredients_is_cacheable(client: TestClient, catalog: dict[str, int]) -> None:
    response = client.get("/ingredients")

    assert response.headers["cache-control"] == "private, max-age=86400"


def test_pantry_starts_empty(client: TestClient, catalog: dict[str, int]) -> None:
    assert client.get("/pantry").json() == []


def test_add_items_returns_the_updated_pantry_sorted(
    client: TestClient, catalog: dict[str, int]
) -> None:
    response = add_items(client, catalog["rice"], catalog["egg"])

    assert response.status_code == 200
    body = response.json()
    assert [item["display_name"] for item in body] == ["Egg", "Rice"]
    assert [item["ingredient_id"] for item in body] == [catalog["egg"], catalog["rice"]]
    # No quantity field anywhere in the API (spec section 4).
    assert set(body[0]) == {"ingredient_id", "display_name", "added_at"}


def test_adding_a_duplicate_leaves_one_row(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    add_items(client, catalog["egg"])
    response = add_items(client, catalog["egg"], catalog["egg"])

    assert response.status_code == 200
    assert len(response.json()) == 1
    count = session.scalar(
        select(func.count())
        .select_from(PantryItem)
        .where(PantryItem.user_id == TEST_USER_ID, PantryItem.ingredient_id == catalog["egg"])
    )
    assert count == 1


def test_unknown_ingredient_ids_are_rejected(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    response = add_items(client, catalog["egg"], 999_999)

    assert response.status_code == 422
    assert response.json()["detail"]["unknown_ingredient_ids"] == [999_999]
    # Nothing is stored when part of the request is invalid.
    assert session.scalar(select(func.count()).select_from(PantryItem)) == 0


def test_empty_and_oversized_requests_are_rejected(client: TestClient) -> None:
    assert client.post("/pantry/items", json={"ingredient_ids": []}).status_code == 422
    assert (
        client.post("/pantry/items", json={"ingredient_ids": list(range(1, 52))}).status_code == 422
    )


def test_delete_removes_an_item_and_is_idempotent(
    client: TestClient, catalog: dict[str, int]
) -> None:
    add_items(client, catalog["egg"], catalog["rice"])

    first = client.delete(f"/pantry/items/{catalog['egg']}")
    second = client.delete(f"/pantry/items/{catalog['egg']}")

    assert first.status_code == 204
    assert second.status_code == 204
    assert [item["display_name"] for item in client.get("/pantry").json()] == ["Rice"]


def test_a_user_cannot_see_another_users_pantry(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    give_other_user(session, catalog["salt"])

    assert client.get("/pantry").json() == []


def test_a_user_cannot_delete_another_users_item(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    give_other_user(session, catalog["salt"])

    response = client.delete(f"/pantry/items/{catalog['salt']}")

    assert response.status_code == 204  # idempotent, but the other user's row survives
    survivor = session.scalar(
        select(func.count())
        .select_from(PantryItem)
        .where(PantryItem.user_id == OTHER_USER_ID, PantryItem.ingredient_id == catalog["salt"])
    )
    assert survivor == 1
