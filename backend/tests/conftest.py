"""Shared test setup (spec 10.6).

The schema is built once per test session with Alembic, against the separate
`scrappy_test` database. Each test then runs inside a transaction that is rolled
back afterwards, so tests never see each other's rows.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.main import app
from app.models import Ingredient, User

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy_test",
)

TEST_USER_ID = "test-user"
OTHER_USER_ID = "other-user"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Migrate the test database to head once, then share one engine for the session."""
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_config, "head")

    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """One test, one transaction: everything written is rolled back at the end."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """An API client that shares the test's session, so its writes roll back too.

    Auth is overridden with a fixed user id: token verification has its own tests.
    """
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    session.add(User(id=TEST_USER_ID))
    session.flush()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def catalog(session: Session) -> dict[str, int]:
    """A small fixture catalog: canonical name -> ingredient id."""
    ingredients = [
        Ingredient(name="egg", display_name="Egg", aliases=["eggs"]),
        Ingredient(name="garlic", display_name="Garlic"),
        Ingredient(name="rice", display_name="Rice"),
        Ingredient(name="salt", display_name="Salt"),
    ]
    session.add_all(ingredients)
    session.flush()
    return {ingredient.name: ingredient.id for ingredient in ingredients}
