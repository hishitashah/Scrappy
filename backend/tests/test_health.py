from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    """Settings are cached per process; clear the cache so each test sees its own env vars."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_returns_ok_with_app_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "abc123")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "abc123"}
