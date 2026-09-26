"""GET /ingredients — the canonical ingredient catalog (spec 10.1)."""

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.auth import CurrentUser, DbSession
from app.models import Ingredient
from app.schemas import IngredientResponse

router = APIRouter(tags=["ingredients"])

# The catalog changes only when the import script runs, and the browser filters it
# locally, so it is worth caching for a day. "private" keeps it out of shared caches.
CACHE_CONTROL = "private, max-age=86400"


@router.get("/ingredients")
def list_ingredients(
    session: DbSession,
    user_id: CurrentUser,
    response: Response,
) -> list[IngredientResponse]:
    """Return every ingredient, ordered by display name."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    ingredients = session.scalars(select(Ingredient).order_by(Ingredient.display_name)).all()
    return [IngredientResponse.model_validate(ingredient) for ingredient in ingredients]
