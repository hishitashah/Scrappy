"""API tests for /grocery-list (F9, spec 10.13).

Mirrors `test_pantry_api.py`, because the endpoint mirrors the pantry's. The tests that
carry their weight are the two the pantry has no equivalent for: that buying something
takes it off the list, and that one user's list is invisible to another.
"""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GroceryItem, User
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


def add_items(client: TestClient, *ingredient_ids: int):
    return client.post("/grocery-list/items", json={"ingredient_ids": list(ingredient_ids)})


def give_other_user(session: Session, ingredient_id: int) -> None:
    """Put one ingredient on a second user's list, to prove the two never mix."""
    session.add(User(id=OTHER_USER_ID))
    session.flush()  # the user row must exist before its grocery row references it
    session.add(GroceryItem(user_id=OTHER_USER_ID, ingredient_id=ingredient_id))
    session.flush()


def rows(session: Session, user_id: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(GroceryItem).where(GroceryItem.user_id == user_id)
        )
        or 0
    )


def test_an_empty_list_is_an_empty_list(client: TestClient) -> None:
    response = client.get("/grocery-list")

    assert response.status_code == 200
    assert response.json() == []


def test_adding_returns_the_list_sorted_by_name(
    client: TestClient, catalog: dict[str, int]
) -> None:
    response = add_items(client, catalog["salt"], catalog["egg"], catalog["garlic"])

    assert response.status_code == 200
    # The order it is shopped in, not the order it was added.
    assert [item["display_name"] for item in response.json()] == ["Egg", "Garlic", "Salt"]


def test_adding_the_same_ingredient_twice_leaves_one_row(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    add_items(client, catalog["egg"])
    response = add_items(client, catalog["egg"])

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert rows(session, TEST_USER_ID) == 1


def test_an_unknown_ingredient_id_is_rejected_and_named(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    """A row pointing at nothing would break every display it appears in."""
    response = add_items(client, catalog["egg"], 999999)

    assert response.status_code == 422
    assert response.json()["detail"]["unknown_ingredient_ids"] == [999999]
    # All or nothing: the valid id in the same request was not saved either.
    assert rows(session, TEST_USER_ID) == 0


def test_an_empty_request_is_rejected(client: TestClient) -> None:
    assert client.post("/grocery-list/items", json={"ingredient_ids": []}).status_code == 422


def test_removing_an_ingredient_is_idempotent(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    add_items(client, catalog["egg"])

    first = client.delete(f"/grocery-list/items/{catalog['egg']}")
    second = client.delete(f"/grocery-list/items/{catalog['egg']}")

    assert (first.status_code, second.status_code) == (204, 204)
    assert rows(session, TEST_USER_ID) == 0


def test_clearing_empties_the_list(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    add_items(client, catalog["egg"], catalog["salt"], catalog["garlic"])

    response = client.delete("/grocery-list")

    assert response.status_code == 204
    assert client.get("/grocery-list").json() == []
    # Idempotent, like the single delete: clearing an empty list is not an error.
    assert client.delete("/grocery-list").status_code == 204


def test_one_user_never_sees_anothers_list(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    give_other_user(session, catalog["egg"])
    add_items(client, catalog["salt"])

    assert [item["display_name"] for item in client.get("/grocery-list").json()] == ["Salt"]


def test_one_user_cannot_remove_from_anothers_list(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    give_other_user(session, catalog["egg"])

    # 204 because the delete is idempotent — but it must not have touched their row.
    assert client.delete(f"/grocery-list/items/{catalog['egg']}").status_code == 204
    assert rows(session, OTHER_USER_ID) == 1


def test_clearing_leaves_another_users_list_intact(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    """The one that would break if `clear` forgot its `where user_id` clause."""
    give_other_user(session, catalog["egg"])
    add_items(client, catalog["salt"])

    assert client.delete("/grocery-list").status_code == 204

    assert rows(session, TEST_USER_ID) == 0
    assert rows(session, OTHER_USER_ID) == 1


def test_buying_an_ingredient_takes_it_off_the_list(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    """The cross-table rule in spec 10.13.

    An ingredient is either something you have or something you need, never both. Adding
    to the pantry deletes from the list in the same transaction, so the two can't drift
    apart and no reconciliation step is needed anywhere else.
    """
    add_items(client, catalog["egg"], catalog["salt"])

    client.post("/pantry/items", json={"ingredient_ids": [catalog["egg"]]})

    # The bought one is gone; the one still needed is untouched.
    assert [item["display_name"] for item in client.get("/grocery-list").json()] == ["Salt"]


def test_buying_leaves_another_users_list_alone(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    give_other_user(session, catalog["egg"])

    client.post("/pantry/items", json={"ingredient_ids": [catalog["egg"]]})

    assert rows(session, OTHER_USER_ID) == 1


def test_an_ingredient_can_be_on_the_list_and_in_another_users_pantry(
    client: TestClient, session: Session, catalog: dict[str, int]
) -> None:
    """The two tables are per-user, so one user's shopping is not another's shopping."""
    from app.models import PantryItem

    session.add(User(id=OTHER_USER_ID))
    session.flush()
    session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=catalog["egg"]))
    session.flush()

    assert add_items(client, catalog["egg"]).status_code == 200
    assert rows(session, TEST_USER_ID) == 1
