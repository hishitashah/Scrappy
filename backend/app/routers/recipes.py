"""GET /recipes/{id} — one recipe in full (spec 10.3)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, DbSession
from app.models import Ingredient, PantryItem, Recipe, RecipeIngredient
from app.schemas import RecipeDetailResponse, RecipeIngredientResponse

router = APIRouter(tags=["recipes"])

GENERATED = "generated"


def _visible_recipe(session: Session, recipe_id: int, user_id: str) -> Recipe:
    """Fetch a recipe the caller may see, or raise 404.

    The imported catalog is shared. A generated recipe (F8) belongs to one user, and to
    everyone else it simply doesn't exist.
    """
    recipe = session.scalar(
        select(Recipe).where(
            Recipe.id == recipe_id,
            or_(Recipe.source != GENERATED, Recipe.created_by == user_id),
        )
    )
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, session: DbSession, user_id: CurrentUser) -> RecipeDetailResponse:
    """Return the recipe with its ingredients in display order, each marked owned or not."""
    recipe = _visible_recipe(session, recipe_id, user_id)

    owned_ids = set(
        session.scalars(select(PantryItem.ingredient_id).where(PantryItem.user_id == user_id)).all()
    )
    rows = session.execute(
        select(Ingredient.id, Ingredient.display_name, RecipeIngredient.measure)
        .join(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.position)
    ).all()

    return RecipeDetailResponse(
        id=recipe.id,
        title=recipe.title,
        category=recipe.category,
        area=recipe.area,
        image_url=recipe.image_url,
        youtube_url=recipe.youtube_url,
        source_url=recipe.source_url,
        steps=recipe.steps,
        ingredients=[
            RecipeIngredientResponse(
                id=row.id,
                display_name=row.display_name,
                measure=row.measure,
                owned=row.id in owned_ids,
            )
            for row in rows
        ],
    )
