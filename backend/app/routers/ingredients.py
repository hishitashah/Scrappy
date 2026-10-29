"""GET /ingredients — the canonical ingredient catalog (spec 10.1)."""

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.auth import CurrentUser, DbSession
from app.models import Ingredient, RecipeIngredient
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
    """Every ingredient that appears in at least one recipe, with its recipe count.

    Ingredients used by no recipe are left out: they can never contribute to a match, so
    offering one is a trap rather than a choice. The count lets the browser rank the
    generic ingredient above its rare variants.
    """
    response.headers["Cache-Control"] = CACHE_CONTROL

    recipe_count = func.count(RecipeIngredient.recipe_id).label("recipe_count")
    rows = session.execute(
        select(Ingredient, recipe_count)
        .join(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .group_by(Ingredient.id)
        .order_by(Ingredient.display_name)
    ).all()

    return [
        IngredientResponse(
            id=ingredient.id,
            name=ingredient.name,
            display_name=ingredient.display_name,
            aliases=ingredient.aliases,
            recipe_count=count,
        )
        for ingredient, count in rows
    ]
