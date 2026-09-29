"""Request logging and error handling (spec 10.9).

Every request writes one JSON line: method, path, status, duration and user. JSON because
these lines land in CloudWatch, where Logs Insights can query fields directly
(`fields path, duration_ms | filter status >= 500`) instead of parsing text.

View them in production with: aws logs tail /aws/lambda/scrappy-api --follow
"""

import json
import logging
import sys
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("scrappy")

# Keys the formatter copies from the log record when present.
_EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "user")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the request fields flattened to the top level."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Send our logs to stdout as JSON, which is what Lambda forwards to CloudWatch."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False

    # Uvicorn logs its own access line; ours carries more, so silence the duplicate.
    logging.getLogger("uvicorn.access").disabled = True


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one line per request, whatever the outcome."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[object]]):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The handler below turns this into a 500; record the timing either way.
            self._log(request, status=500, started=started, level=logging.ERROR)
            raise

        self._log(request, status=response.status_code, started=started)
        return response

    def _log(
        self, request: Request, *, status: int, started: float, level: int = logging.INFO
    ) -> None:
        logger.log(
            level,
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                # Set by get_current_user; absent on /health and on rejected requests.
                "user": getattr(request.state, "user_id", None),
            },
        )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the stack trace, return a body that says nothing about our internals."""
    logger.exception(
        "unhandled error",
        extra={"method": request.method, "path": request.url.path, "status": 500},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


def install(app: FastAPI) -> None:
    """Wire logging, the request middleware and the error handler into the app."""
    configure_logging()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(Exception, unhandled_exception_handler)
