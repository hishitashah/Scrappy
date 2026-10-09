"""SQLAlchemy engine and per-request sessions.

The engine owns a pool of database connections and is created once per process. A
session is one unit of work: it is opened for a request, used, and closed afterwards.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings


def engine_options(url: str) -> dict[str, Any]:
    """Connection settings for a database URL (spec 10.7).

    Against Neon the app runs on Lambda behind a connection pooler, which changes three
    things. Each Lambda instance handles one request at a time, so a pool larger than one
    connection only wastes Postgres's limited connection slots. Neon suspends after five
    minutes idle, so a pooled connection may be dead by the time it is reused, which
    `pool_pre_ping` catches. And psycopg 3's server-side prepared statements break behind a
    pooler, because a later query can land on a different backend session than the one that
    prepared the statement — `prepare_threshold=None` turns them off.
    """
    options: dict[str, Any] = {"pool_pre_ping": True}

    if "neon.tech" in url:
        options |= {
            "pool_size": 1,
            "max_overflow": 0,
            "connect_args": {"prepare_threshold": None, "sslmode": "require"},
        }
    return options


@lru_cache
def get_engine() -> Engine:
    """Create the engine once per process and reuse it."""
    url = get_settings().database_url
    return create_engine(url, **engine_options(url))


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with _session_factory()() as session:
        yield session
