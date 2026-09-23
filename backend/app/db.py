"""SQLAlchemy engine and per-request sessions.

The engine owns a pool of database connections and is created once per process. A
session is one unit of work: it is opened for a request, used, and closed afterwards.
Neon-specific pool settings (spec 10.7) are added when the app moves to Lambda.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the engine once per process and reuse it."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with _session_factory()() as session:
        yield session
