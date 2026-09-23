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
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://scrappy:scrappy@localhost:5432/scrappy_test",
)


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
