"""Configuration resolution, including the production SSM lookup (spec 10.7, 13)."""

from collections.abc import Iterator
from typing import Any

import pytest

from app import settings as settings_module
from app.db import engine_options
from app.settings import Settings, get_settings

NEON_URL = "postgresql+psycopg://u:p@ep-cool-name-pooler.us-east-1.aws.neon.tech/scrappy"
LOCAL_URL = "postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy"


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeSsm:
    """Stands in for boto3: tests never call AWS."""

    def __init__(self, value: str) -> None:
        self.value = value
        self.calls: list[str] = []

    def __call__(self, name: str) -> str:
        self.calls.append(name)
        return self.value


def test_database_url_is_used_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local and CI set DATABASE_URL directly; SSM is never consulted."""
    fake = FakeSsm("should-not-be-used")
    monkeypatch.setattr(settings_module, "_read_ssm_parameter", fake)
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setenv("DATABASE_URL_PARAM", "/scrappy/prod/database_url")

    assert get_settings().database_url == LOCAL_URL
    assert fake.calls == []


def test_the_url_comes_from_ssm_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSsm(NEON_URL)
    monkeypatch.setattr(settings_module, "_read_ssm_parameter", fake)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_PARAM", "/scrappy/prod/database_url")

    assert get_settings().database_url == NEON_URL
    assert fake.calls == ["/scrappy/prod/database_url"]


def test_ssm_is_read_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cache is what keeps a warm Lambda from fetching on every request."""
    fake = FakeSsm(NEON_URL)
    monkeypatch.setattr(settings_module, "_read_ssm_parameter", fake)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_PARAM", "/scrappy/prod/database_url")

    for _ in range(3):
        get_settings()

    assert len(fake.calls) == 1


def test_no_ssm_lookup_without_the_parameter_name(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSsm("unused")
    monkeypatch.setattr(settings_module, "_read_ssm_parameter", fake)
    monkeypatch.delenv("DATABASE_URL_PARAM", raising=False)

    get_settings()

    assert fake.calls == []


def _connect_args(options: dict[str, Any]) -> dict[str, Any]:
    return dict(options.get("connect_args", {}))


def test_engine_options_for_neon() -> None:
    """Behind the pooler: one connection, and no server-side prepared statements."""
    options = engine_options(NEON_URL)

    assert options["pool_size"] == 1
    assert options["max_overflow"] == 0
    assert options["pool_pre_ping"] is True
    assert _connect_args(options) == {"prepare_threshold": None, "sslmode": "require"}


def test_engine_options_for_local_postgres_are_left_alone() -> None:
    options = engine_options(LOCAL_URL)

    assert options == {"pool_pre_ping": True}


def test_settings_defaults_have_no_ssm_parameter() -> None:
    assert Settings(_env_file=None).database_url_param is None
