"""The grocery list: what the current user still needs to buy (F9, spec 10.13).

Structurally the pantry's twin, and for the same reason — every query is filtered by the
caller's user id, which is what stops one user reading or changing another's list.

The list only ever shrinks on its own: adding an ingredient to the pantry deletes it from
here, in `POST /pantry/items`, so an ingredient is never both owned and still to buy.
"""

from fastapi import APIRouter, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import CurrentUser, DbSession
from app.catalog import assert_known_ingredients
from app.models import GroceryItem, Ingredient
from app.schemas import AddGroceryItemsRequest, GroceryItemResponse

router = APIRouter(tags=["grocery"])


def read_grocery_list(session: Session, user_id: str) -> list[GroceryItemResponse]:
    """The user's list, sorted by display name — the order it is shopped in."""
    rows = session.execute(
        select(GroceryItem.ingredient_id, Ingredient.display_name, GroceryItem.added_at)
        .join(Ingredient, Ingredient.id == GroceryItem.ingredient_id)
        .where(GroceryItem.user_id == user_id)
        .order_by(Ingredient.display_name)
    ).all()
    return [
        GroceryItemResponse(
            ingredient_id=row.ingredient_id, display_name=row.display_name, added_at=row.added_at
        )
        for row in rows
    ]


@router.get("/grocery-list")
def get_grocery_list(session: DbSession, user_id: CurrentUser) -> list[GroceryItemResponse]:
    return read_grocery_list(session, user_id)


@router.post("/grocery-list/items")
def add_grocery_items(
    payload: AddGroceryItemsRequest,
    session: DbSession,
    user_id: CurrentUser,
) -> list[GroceryItemResponse]:
    """Add ingredients to the list and return the updated list.

    Validated exactly as the pantry is: only catalog ingredients, unknown ids rejected,
    ids already on the list ignored.
    """
    requested = assert_known_ingredients(session, payload.ingredient_ids)

    session.execute(
        insert(GroceryItem)
        .values([{"user_id": user_id, "ingredient_id": i} for i in requested])
        .on_conflict_do_nothing()
    )
    session.commit()
    return read_grocery_list(session, user_id)


@router.delete("/grocery-list/items/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_grocery_item(ingredient_id: int, session: DbSession, user_id: CurrentUser) -> None:
    """Remove one ingredient. Idempotent: removing what isn't there still returns 204."""
    session.execute(
        delete(GroceryItem).where(
            GroceryItem.user_id == user_id, GroceryItem.ingredient_id == ingredient_id
        )
    )
    session.commit()


@router.delete("/grocery-list", status_code=status.HTTP_204_NO_CONTENT)
def clear_grocery_list(session: DbSession, user_id: CurrentUser) -> None:
    """Empty the caller's list in one statement.

    Spec 10.13 asks for a "Clear list" button but section 11 defines no endpoint that can
    serve it. The alternative — one delete per row from the browser — can fail halfway and
    leave a half-cleared list, for no benefit. Idempotent, like the single delete.
    """
    session.execute(delete(GroceryItem).where(GroceryItem.user_id == user_id))
    session.commit()
