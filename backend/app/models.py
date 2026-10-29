"""ORM table definitions (spec section 12). Alembic migrations are generated from these."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
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
    # Null for imported recipes; the owner for AI-generated ones (F8, spec 10.12).
    # Matching hides a generated recipe from everyone except this user.
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
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


class AiMonthlyUsage(Base):
    """What every AI call this month has cost, in one row (spec 12, 14).

    `cost_cents` is not a running sum of per-call costs: one substitution costs about a
    cent, so rounding each call to an integer would lose a tenth of the spend every time,
    and a sub-cent call would add nothing at all. A monthly cap fed by rounded-down pennies
    could never fire. Instead the token totals are accumulated — they are exact integers —
    and the cost is recomputed from them on every write.
    """

    __tablename__ = "ai_monthly_usage"

    month: Mapped[str] = mapped_column(String(7), primary_key=True)  # "YYYY-MM", UTC
    calls: Mapped[int] = mapped_column(server_default="0")
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    # Compared against AI_MONTHLY_BUDGET_CENTS before every call that would spend.
    cost_cents: Mapped[int] = mapped_column(server_default="0")


class AiUserDailyUsage(Base):
    """One user's calls today, per feature — the per-user fairness limit (spec 14)."""

    __tablename__ = "ai_user_daily_usage"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)  # UTC
    # "substitutions" (F7) or "generation" (F8).
    feature: Mapped[str] = mapped_column(Text, primary_key=True)
    calls: Mapped[int] = mapped_column(server_default="0")


class SubstitutionCache(Base):
    """Answers already paid for (spec 10.11).

    Keyed by the recipe and a hash of the pantry, because those two are the whole question.
    The key does not include the prompt, so changing the prompt means clearing this table.
    """

    __tablename__ = "substitution_cache"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    # SHA-256 of the caller's sorted pantry ingredient ids.
    pantry_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
