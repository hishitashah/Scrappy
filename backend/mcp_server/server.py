"""The tools (see the package docstring for what MCP is).

This is a second front door onto the code the web API already runs. Every tool calls the
router function behind the matching endpoint, so nothing is reimplemented:

- ranking is still the one SQL query in `app/matching.py`, with the same 50% floor and the
  same assumed staples;
- a name the catalog doesn't know is still refused rather than stored;
- adding to the pantry still takes the item off the grocery list in the same transaction;
- a generated recipe is still invisible to everyone but its owner.

The server makes no AI call of its own. The assistant on the other end is the model; the
server only counts and stores, which keeps spec section 4's rule (counting for facts,
models for judgment) and leaves the $5/month guardrails of spec section 14 untouched.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Annotated

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.catalog import find_ingredient_ids
from app.models import Ingredient, RecipeIngredient
from app.normalize import normalize
from app.routers import grocery, matches, pantry, recipes
from app.schemas import (
    AddGroceryItemsRequest,
    AddPantryItemsRequest,
    GroceryItemResponse,
    PantryItemResponse,
    RecipeDetailResponse,
)

# Opens one database session per tool call. Production passes `lambda: Session(engine)`;
# tests pass their own rolled-back session, so a tool's writes vanish with the test.
SessionFactory = Callable[[], AbstractContextManager[Session]]

INSTRUCTIONS = """\
Scrappy keeps one cook's pantry and ranks recipes by how many of each recipe's ingredients
they already have. Typical flow: add_to_pantry with what they bought, find_recipes,
get_recipe for the one they pick, then add_missing_to_grocery_list. Ingredient names must
match the catalog; when add_to_pantry reports a name as not_found, call search_ingredients
to find the catalog's name for it. Water, salt, pepper, cooking oil and butter are assumed
to be in every kitchen, so they never need adding."""

READ_ONLY = ToolAnnotations(read_only_hint=True)
WRITES = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True)
REMOVES = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True)


class Item(BaseModel):
    """One ingredient in the pantry or on the grocery list."""

    ingredient_id: int
    name: str


class PantryUpdate(BaseModel):
    pantry: list[Item]
    added: list[str] = Field(description="Catalog names of the ingredients now in the pantry")
    not_found: list[str] = Field(description="Names given that match no catalog ingredient")


class RecipeMatch(BaseModel):
    recipe_id: int
    title: str
    match_percent: int
    have: int
    total: int
    missing: list[str]
    ai_written: bool = Field(description="One of this cook's own AI-generated recipes")


class RecipeLine(BaseModel):
    name: str
    measure: str | None
    have: bool


class RecipeDetail(BaseModel):
    recipe_id: int
    title: str
    category: str | None
    area: str | None
    ai_written: bool
    ingredients: list[RecipeLine]
    missing: list[str]
    steps: list[str]


class GroceryUpdate(BaseModel):
    grocery_list: list[Item]
    added: list[str]


class IngredientSuggestion(BaseModel):
    ingredient_id: int
    name: str
    recipe_count: int


def build_server(session_factory: SessionFactory, user_id: str) -> MCPServer:
    """Build the server for one cook. Every tool reads and writes only `user_id`'s rows."""
    server = MCPServer(name="scrappy", instructions=INSTRUCTIONS)

    def visible_recipe(session: Session, recipe_id: int) -> RecipeDetailResponse:
        """The recipe as `GET /recipes/{id}` returns it, or an error the model can read."""
        try:
            return recipes.get_recipe(recipe_id, session, user_id)
        except HTTPException as error:
            # 404 covers "doesn't exist" and "another cook's generated recipe" alike, so
            # the tool can't be used to discover that someone else's recipe exists.
            raise ToolError(f"No recipe with id {recipe_id}.") from error

    @server.tool(annotations=READ_ONLY)
    def get_pantry() -> list[Item]:
        """List the ingredients in the cook's pantry."""
        with session_factory() as session:
            return [_item(row) for row in pantry.read_pantry(session, user_id)]

    @server.tool(annotations=WRITES)
    def add_to_pantry(
        ingredients: Annotated[list[str], Field(min_length=1, max_length=50)],
    ) -> PantryUpdate:
        """Add ingredients to the pantry by name, e.g. ["eggs", "spinach"].

        Also takes them off the grocery list, since they've been bought. Names that match
        no catalog ingredient are not added; they come back in `not_found`.
        """
        with session_factory() as session:
            found = find_ingredient_ids(session, ingredients)
            ids = [found[name] for name in ingredients if name in found]
            not_found = [name for name in ingredients if name not in found]
            if ids:
                rows = pantry.add_pantry_items(
                    AddPantryItemsRequest(ingredient_ids=ids), session, user_id
                )
            else:
                rows = pantry.read_pantry(session, user_id)
            names = {row.ingredient_id: row.display_name for row in rows}
            return PantryUpdate(
                pantry=[_item(row) for row in rows],
                added=list(dict.fromkeys(names[i] for i in ids)),
                not_found=not_found,
            )

    @server.tool(annotations=REMOVES)
    def remove_from_pantry(ingredient: str) -> list[Item]:
        """Remove one ingredient from the pantry by name. Returns the updated pantry."""
        with session_factory() as session:
            ingredient_id = find_ingredient_ids(session, [ingredient]).get(ingredient)
            current = {row.ingredient_id for row in pantry.read_pantry(session, user_id)}
            if ingredient_id not in current:
                raise ToolError(f"{ingredient!r} is not in the pantry.")
            pantry.remove_pantry_item(ingredient_id, session, user_id)
            return [_item(row) for row in pantry.read_pantry(session, user_id)]

    @server.tool(annotations=READ_ONLY)
    def find_recipes(limit: Annotated[int, Field(ge=1, le=50)] = 10) -> list[RecipeMatch]:
        """Rank recipes by how much of each the cook can make with their pantry.

        Recipes under 50% are left out. `missing` lists what they'd still need to buy.
        """
        with session_factory() as session:
            return [
                RecipeMatch(
                    recipe_id=match.id,
                    title=match.title,
                    match_percent=match.match,
                    have=match.have,
                    total=match.total,
                    missing=match.missing,
                    ai_written=match.generated,
                )
                for match in matches.get_matches(session, user_id, limit)
            ]

    @server.tool(annotations=READ_ONLY)
    def get_recipe(recipe_id: int) -> RecipeDetail:
        """Get one recipe's ingredients (each marked have or missing) and its steps."""
        with session_factory() as session:
            recipe = visible_recipe(session, recipe_id)
            return RecipeDetail(
                recipe_id=recipe.id,
                title=recipe.title,
                category=recipe.category,
                area=recipe.area,
                ai_written=recipe.generated,
                ingredients=[
                    RecipeLine(name=line.display_name, measure=line.measure, have=line.owned)
                    for line in recipe.ingredients
                ],
                missing=[line.display_name for line in recipe.ingredients if not line.owned],
                steps=recipe.steps,
            )

    @server.tool(annotations=WRITES)
    def add_missing_to_grocery_list(recipe_id: int) -> GroceryUpdate:
        """Put every ingredient a recipe needs and the cook doesn't have on the grocery list."""
        with session_factory() as session:
            recipe = visible_recipe(session, recipe_id)
            missing = [line for line in recipe.ingredients if not line.owned]
            if missing:
                rows = grocery.add_grocery_items(
                    AddGroceryItemsRequest(ingredient_ids=[line.id for line in missing]),
                    session,
                    user_id,
                )
            else:
                rows = grocery.read_grocery_list(session, user_id)
            return GroceryUpdate(
                grocery_list=[_item(row) for row in rows],
                added=[line.display_name for line in missing],
            )

    @server.tool(annotations=READ_ONLY)
    def get_grocery_list() -> list[Item]:
        """List what the cook still needs to buy."""
        with session_factory() as session:
            return [_item(row) for row in grocery.read_grocery_list(session, user_id)]

    @server.tool(annotations=READ_ONLY)
    def search_ingredients(
        query: Annotated[str, Field(min_length=1, max_length=100)],
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> list[IngredientSuggestion]:
        """Find catalog ingredients whose name contains `query`, most-used first.

        Use it when add_to_pantry can't place a name: "chicken breasts" might be
        "Chicken Breast" in the catalog.
        """
        canonical = normalize(query)
        if not canonical:
            raise ToolError(f"{query!r} isn't an ingredient name.")
        recipe_count = func.count(RecipeIngredient.recipe_id).label("recipe_count")
        with session_factory() as session:
            rows = session.execute(
                # Only ingredients some recipe uses, as `GET /ingredients` returns: one no
                # recipe uses can never contribute to a match.
                select(Ingredient.id, Ingredient.display_name, recipe_count)
                .join(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.id)
                .where(
                    or_(
                        Ingredient.name.contains(canonical, autoescape=True),
                        Ingredient.display_name.icontains(query.strip(), autoescape=True),
                    )
                )
                .group_by(Ingredient.id)
                .order_by(recipe_count.desc(), Ingredient.display_name)
                .limit(limit)
            ).all()
            return [
                IngredientSuggestion(
                    ingredient_id=row.id, name=row.display_name, recipe_count=row.recipe_count
                )
                for row in rows
            ]

    return server


def _item(row: PantryItemResponse | GroceryItemResponse) -> Item:
    return Item(ingredient_id=row.ingredient_id, name=row.display_name)
