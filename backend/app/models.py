"""ORM table definitions (spec section 12). Alembic migrations are generated from these."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint and index names, so Alembic migrations can always refer to them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Ingredient(Base):
    """One canonical ingredient. Recipe lines and pantry items both point here."""

    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Normalized by app/normalize.py: lowercase and singular, e.g. "chicken breast".
    name: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    # Extra autocomplete terms, e.g. {"eggs"}.
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")


class Recipe(Base):
    __tablename__ = "recipes"
    # One row per recipe per source, so re-running the import updates instead of duplicating.
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(Text)  # "themealdb"
    source_id: Mapped[str | None] = mapped_column(Text)  # TheMealDB's idMeal
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    youtube_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[str]] = mapped_column(JSONB)
    # TheMealDB provides neither, so both stay empty in the MVP (spec section 4).
    total_minutes: Mapped[int | None] = mapped_column()
    servings: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipeIngredient(Base):
    """One line of a recipe's ingredient list."""

    __tablename__ = "recipe_ingredients"
    # Matching filters by ingredient, which the primary key alone can't serve (spec 10.2).
    __table_args__ = (Index("ix_recipe_ingredients_ingredient_id", "ingredient_id"),)

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), primary_key=True)
    # Display only: never parsed or compared, because quantities aren't tracked.
    measure: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int | None] = mapped_column(SmallInteger)


class User(Base):
    __tablename__ = "users"

    # The Cognito `sub`, or "shared-user" before login ships (spec 10.4).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PantryItem(Base):
    """One ingredient a user has. There is no quantity column, by design (spec section 4)."""

    __tablename__ = "pantry_items"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
