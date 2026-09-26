"""Pydantic request and response models for the API (spec section 11)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class PantryItemResponse(BaseModel):
    """One ingredient a user has. There is no quantity field, by design (spec section 4)."""

    model_config = ConfigDict(from_attributes=True)

    ingredient_id: int
    display_name: str
    added_at: datetime


class AddPantryItemsRequest(BaseModel):
    ingredient_ids: list[int] = Field(min_length=1, max_length=50)
