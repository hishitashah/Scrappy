"""API tests for /me — the caller's preferred store (F9, spec 10.13)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from app.stores import STORE_KEYS
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


def test_no_store_is_chosen_to_begin_with(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 200
    # Null, not a default chain: the list shows "Pick a store" rather than guessing.
    assert response.json() == {"preferred_store": None}


def test_a_chosen_store_is_saved_and_read_back(client: TestClient, session: Session) -> None:
    response = client.patch("/me", json={"preferred_store": "walmart"})

    assert response.status_code == 200
    assert response.json() == {"preferred_store": "walmart"}
    # Stored server-side, so the choice follows the user between devices.
    assert client.get("/me").json() == {"preferred_store": "walmart"}
    assert session.get(User, TEST_USER_ID).preferred_store == "walmart"


def test_a_store_can_be_changed(client: TestClient) -> None:
    client.patch("/me", json={"preferred_store": "walmart"})

    assert client.patch("/me", json={"preferred_store": "publix"}).status_code == 200
    assert client.get("/me").json() == {"preferred_store": "publix"}


def test_a_store_can_be_cleared(client: TestClient) -> None:
    client.patch("/me", json={"preferred_store": "target"})

    response = client.patch("/me", json={"preferred_store": None})

    assert response.status_code == 200
    assert response.json() == {"preferred_store": None}


@pytest.mark.parametrize("key", STORE_KEYS)
def test_every_chain_in_the_catalog_is_accepted(client: TestClient, key: str) -> None:
    """Catches a key that exists in the picker but was never allowed by the API."""
    assert client.patch("/me", json={"preferred_store": key}).status_code == 200


@pytest.mark.parametrize("key", ["tesco", "WALMART", "walmart ", "", "aldi"])
def test_an_unknown_store_is_rejected(client: TestClient, session: Session, key: str) -> None:
    """Including near-misses: the key is what the frontend's URL table is indexed by."""
    response = client.patch("/me", json={"preferred_store": key})

    assert response.status_code == 422
    assert session.get(User, TEST_USER_ID).preferred_store is None


def test_one_user_cannot_change_anothers_store(client: TestClient, session: Session) -> None:
    session.add(User(id=OTHER_USER_ID, preferred_store="kroger"))
    session.flush()

    client.patch("/me", json={"preferred_store": "walmart"})

    assert session.get(User, OTHER_USER_ID).preferred_store == "kroger"
