"""Auth-mode tests (spec 10.4). Cognito token verification is tested in M5."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import SHARED_USER_ID, get_current_user
from app.db import get_session
from app.main import app
from app.models import User
from app.settings import Settings, get_settings


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
    user_id = get_current_user(session, Settings(env="local", auth_mode="shared"))

    assert user_id == SHARED_USER_ID


def test_cognito_mode_is_not_implemented_yet(session: Session) -> None:
    with pytest.raises(NotImplementedError):
        get_current_user(session, Settings(env="local", auth_mode="cognito"))


def test_production_refuses_shared_mode() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=shared is not allowed"):
        Settings(env="prod", auth_mode="shared", allow_shared_mode=False)


def test_production_allows_shared_mode_with_the_override() -> None:
    settings = Settings(env="prod", auth_mode="shared", allow_shared_mode=True)

    assert settings.auth_mode == "shared"


def test_production_allows_cognito_mode() -> None:
    settings = Settings(env="prod", auth_mode="cognito")

    assert settings.auth_mode == "cognito"
