"""Pydantic request and response models for the API (spec section 11)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.stores import StoreKey


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


class IngredientResponse(BaseModel):
    """One catalog ingredient. The browser downloads the whole list once (spec 10.1)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    aliases: list[str]
    # How many recipes use it. The browser ranks suggestions by this, so "Eggs" (218
    # recipes) is offered before "Free-range Egg, Beaten" (2) for the same typing.
    recipe_count: int


class PantryItemResponse(BaseModel):
    """One ingredient a user has. There is no quantity field, by design (spec section 4)."""

    model_config = ConfigDict(from_attributes=True)

    ingredient_id: int
    display_name: str
    added_at: datetime


class AddPantryItemsRequest(BaseModel):
    ingredient_ids: list[int] = Field(min_length=1, max_length=50)


class GroceryItemResponse(BaseModel):
    """One ingredient still to buy (spec 10.13).

    The same three fields as `PantryItemResponse` and still its own model: these are two
    different things in `/openapi.json`, and sharing a name would make the generated docs
    claim an endpoint returns the other one.
    """

    model_config = ConfigDict(from_attributes=True)

    ingredient_id: int
    display_name: str
    added_at: datetime


class AddGroceryItemsRequest(BaseModel):
    ingredient_ids: list[int] = Field(min_length=1, max_length=50)


class MeResponse(BaseModel):
    """The caller's own settings (spec 10.13). Null means no store has been chosen."""

    preferred_store: str | None


class UpdateMeRequest(BaseModel):
    """A store key from `app/stores.py`, or null to clear it.

    Validated here rather than in the handler so that the allowed values are part of the
    published schema: `/docs` lists them, and a bad key is a 422 before any code runs.
    """

    preferred_store: StoreKey | None = None


class MatchResponse(BaseModel):
    """One ranked recipe (spec 10.2). `match` is a whole-number percentage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    thumbnail_url: str | None
    have: int
    total: int
    match: int
    missing: list[str]
    # True for an AI-written recipe (F8), which the card labels. Always this user's own:
    # matching never shows one belonging to anyone else.
    generated: bool


class RecipeIngredientResponse(BaseModel):
    """One line of a recipe's ingredient list, with the measure shown as written."""

    id: int
    display_name: str
    measure: str | None
    owned: bool


class RecipeDetailResponse(BaseModel):
    """A full recipe (spec 10.3). Times and servings are absent, not invented."""

    id: int
    title: str
    category: str | None
    area: str | None
    image_url: str | None
    youtube_url: str | None
    source_url: str | None
    steps: list[str]
    # True for an AI-written recipe (F8). The page shows a badge in place of the category
    # and cuisine tags, which a generated recipe doesn't have.
    generated: bool
    ingredients: list[RecipeIngredientResponse]


class SubstitutionResponse(BaseModel):
    """One AI substitution (spec 10.11).

    `in_pantry` is computed by the API, not asked of the model: whether the user owns the
    suggested ingredient is a fact to be counted, not a judgment (spec section 4).
    """

    missing_ingredient: str
    suggestion: str
    reason: str
    in_pantry: bool


class SubstitutionsResponse(BaseModel):
    """Wrapped in an object rather than returned as a bare list, so that fields can be
    added later (a cache flag, a model name) without breaking the client."""

    suggestions: list[SubstitutionResponse]
