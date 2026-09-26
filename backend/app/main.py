"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import ingredients, matches, pantry, recipes
from app.schemas import HealthResponse
from app.settings import get_settings

settings = get_settings()

app = FastAPI(title="Scrappy API")

# CORS lives in exactly one place (spec 10.7): the Lambda Function URL handles it in
# production, so enabling it here too would send duplicate headers that browsers reject.
if settings.env == "local":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["authorization", "content-type"],
    )

app.include_router(ingredients.router)
app.include_router(pantry.router)
app.include_router(matches.router)
app.include_router(recipes.router)


@app.get("/health")
def health() -> HealthResponse:
    """Liveness check. Never touches the database, so it doesn't wake Neon (spec 10.9)."""
    return HealthResponse(status="ok", version=get_settings().app_version)
