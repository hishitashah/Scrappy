"""Schema behavior: the constraints in spec section 12 are actually enforced."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Ingredient, PantryItem, Recipe, RecipeIngredient, User


def make_ingredient(session: Session, name: str) -> Ingredient:
    ingredient = Ingredient(name=name, display_name=name.title())
    session.add(ingredient)
    session.flush()
    return ingredient


def make_recipe(session: Session, title: str, source_id: str) -> Recipe:
    recipe = Recipe(source="themealdb", source_id=source_id, title=title, steps=["Cook it."])
    session.add(recipe)
    session.flush()
    return recipe


def test_ingredient_name_is_unique(session: Session) -> None:
    make_ingredient(session, "egg")
    session.add(Ingredient(name="egg", display_name="Egg"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_ingredient_defaults_to_no_aliases(session: Session) -> None:
    ingredient = make_ingredient(session, "rice")
    session.refresh(ingredient)

    assert ingredient.aliases == []


def test_recipe_is_unique_per_source_and_source_id(session: Session) -> None:
    make_recipe(session, "Boiled egg", "52001")
    session.add(Recipe(source="themealdb", source_id="52001", title="Boiled egg", steps=[]))

    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_recipe_deletes_its_ingredient_rows(session: Session) -> None:
    recipe = make_recipe(session, "Boiled egg", "52002")
    egg = make_ingredient(session, "egg")
    session.add(
        RecipeIngredient(recipe_id=recipe.id, ingredient_id=egg.id, measure="2", position=0)
    )
    session.flush()

    session.delete(recipe)
    session.flush()

    remaining = session.scalars(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).all()
    assert remaining == []
    # The ingredient itself survives; other recipes still use it.
    assert session.get(Ingredient, egg.id) is not None


def test_pantry_cannot_hold_the_same_ingredient_twice(session: Session) -> None:
    session.add(User(id="user-1"))
    egg = make_ingredient(session, "egg")
    session.add(PantryItem(user_id="user-1", ingredient_id=egg.id))
    session.flush()

    session.add(PantryItem(user_id="user-1", ingredient_id=egg.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_deleting_a_user_deletes_their_pantry(session: Session) -> None:
    user = User(id="user-2")
    session.add(user)
    egg = make_ingredient(session, "egg")
    session.add(PantryItem(user_id="user-2", ingredient_id=egg.id))
    session.flush()

    session.delete(user)
    session.flush()

    remaining = session.scalars(select(PantryItem).where(PantryItem.user_id == "user-2")).all()
    assert remaining == []


def test_recipe_steps_round_trip_as_a_list(session: Session) -> None:
    recipe = Recipe(
        source="themealdb",
        source_id="52003",
        title="Pancakes",
        steps=["Mix.", "Fry.", "Serve."],
    )
    session.add(recipe)
    session.flush()
    session.refresh(recipe)

    assert recipe.steps == ["Mix.", "Fry.", "Serve."]
    assert recipe.created_at is not None
    # TheMealDB has neither, so they stay empty (spec section 4).
    assert recipe.total_minutes is None
    assert recipe.servings is None
