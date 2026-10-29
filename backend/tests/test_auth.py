"""Auth-mode tests (spec 10.4). Cognito token verification is tested in M5."""

from collections.abc import Iterator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import SHARED_USER_ID, get_current_user
from app.db import get_session
from app.main import app
from app.models import User
from app.settings import Settings, get_settings


def fake_request() -> Request:
    """A bare request, enough for the dependency to record the user on `state`."""
    return Request({"type": "http", "method": "GET", "path": "/pantry", "headers": []})


@pytest.fixture
def shared_mode_client(session: Session) -> Iterator[TestClient]:
    """A client using the real get_current_user dependency, in shared mode."""
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: Settings(env="local", auth_mode="shared")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_shared_mode_creates_the_shared_user_once(
    shared_mode_client: TestClient, session: Session
) -> None:
    assert shared_mode_client.get("/pantry").status_code == 200
    assert shared_mode_client.get("/pantry").status_code == 200

    count = session.scalar(select(func.count()).select_from(User).where(User.id == SHARED_USER_ID))
    assert count == 1


def test_shared_mode_returns_the_fixed_user(session: Session) -> None:
    request = fake_request()

    user_id = get_current_user(request, session, Settings(env="local", auth_mode="shared"))

    assert user_id == SHARED_USER_ID
    # The request log line reads the user from here (spec 10.9).
    assert request.state.user_id == SHARED_USER_ID


def test_production_refuses_shared_mode() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=shared is not allowed"):
        Settings(env="prod", auth_mode="shared", allow_shared_mode=False)


def test_production_allows_shared_mode_with_the_override() -> None:
    settings = Settings(env="prod", auth_mode="shared", allow_shared_mode=True)

    assert settings.auth_mode == "shared"


def test_production_allows_cognito_mode() -> None:
    settings = Settings(
        env="prod",
        auth_mode="cognito",
        cognito_user_pool_id="us-east-1_test",
        cognito_client_id="client123",
    )

    assert settings.auth_mode == "cognito"


def test_cognito_mode_requires_the_pool_settings() -> None:
    """A half-configured pool is a startup error, not a surprise on the first request.

    `_env_file=None` keeps the assertion honest: without it the test would read the
    developer's own backend/.env and pass for the wrong reason.
    """
    with pytest.raises(ValueError, match="requires COGNITO_USER_POOL_ID"):
        Settings(_env_file=None, env="local", auth_mode="cognito")
