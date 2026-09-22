"""FastAPI application entry point."""

from fastapi import FastAPI

from app.schemas import HealthResponse
from app.settings import get_settings

app = FastAPI(title="Scrappy API")


@app.get("/health")
def health() -> HealthResponse:
    """Liveness check. Never touches the database, so it doesn't wake Neon (spec 10.9)."""
    return HealthResponse(status="ok", version=get_settings().app_version)
