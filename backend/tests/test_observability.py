"""Request logging and error handling (spec 10.9)."""

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter, logger


@pytest.fixture
def log_records(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    """Capture our logger, which is deliberately detached from the root logger."""
    logger.propagate = True
    with caplog.at_level(logging.INFO, logger="scrappy"):
        yield caplog
    logger.propagate = False


def request_lines(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.message == "request"]


def test_every_request_logs_one_line(
    client: TestClient, log_records: pytest.LogCaptureFixture, catalog: dict[str, int]
) -> None:
    client.get("/ingredients")

    lines = request_lines(log_records)
    assert len(lines) == 1
    record = lines[0]
    assert record.method == "GET"
    assert record.path == "/ingredients"
    assert record.status == 200
    assert record.duration_ms >= 0
    assert record.levelno == logging.INFO


def test_the_line_names_the_user(
    client: TestClient, log_records: pytest.LogCaptureFixture, catalog: dict[str, int]
) -> None:
    """Logs say who a request belonged to, which is how a live issue gets traced."""
    client.get("/pantry")

    assert request_lines(log_records)[0].user == "test-user"


def test_health_is_logged_without_a_user(
    client: TestClient, log_records: pytest.LogCaptureFixture
) -> None:
    """/health needs no auth and touches no database, so it has no user."""
    client.get("/health")

    record = request_lines(log_records)[0]
    assert record.path == "/health"
    assert record.user is None


def test_a_404_is_logged_at_info_not_error(
    client: TestClient, log_records: pytest.LogCaptureFixture
) -> None:
    """A missing recipe is a normal answer, not an incident."""
    client.get("/recipes/999999")

    record = request_lines(log_records)[0]
    assert record.status == 404
    assert record.levelno == logging.INFO


def test_an_unexpected_error_returns_a_safe_body_and_logs_the_trace(
    log_records: pytest.LogCaptureFixture,
) -> None:
    @app.get("/boom-for-tests")
    def boom() -> None:
        raise RuntimeError("database on fire")

    # This client lets the app's own handler answer instead of re-raising into the test.
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.get("/boom-for-tests")

        assert response.status_code == 500
        # Nothing about our internals reaches the caller.
        assert response.json() == {"detail": "Internal error"}
        assert "database on fire" not in response.text

        errors = [r for r in log_records.records if r.levelno == logging.ERROR]
        assert any(r.exc_info for r in errors), "the stack trace should be logged"
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", "") != "/boom-for-tests"
        ]


def test_the_formatter_emits_one_json_object_per_line() -> None:
    record = logging.LogRecord("scrappy", logging.INFO, __file__, 1, "request", None, None)
    record.method, record.path, record.status, record.duration_ms = "GET", "/pantry", 200, 12.3
    record.user = "test-user"

    line = JsonFormatter().format(record)

    assert "\n" not in line
    assert json.loads(line) == {
        "level": "INFO",
        "logger": "scrappy",
        "message": "request",
        "method": "GET",
        "path": "/pantry",
        "status": 200,
        "duration_ms": 12.3,
        "user": "test-user",
    }
