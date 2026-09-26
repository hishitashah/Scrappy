"""The pantry: what the current user has (spec 10.1).

Every query is filtered by the caller's user id, which is what stops one user from
reading or changing another's pantry.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import CurrentUser, DbSession
from app.models import Ingredient, PantryItem
from app.schemas import AddPantryItemsRequest, PantryItemResponse

router = APIRouter(tags=["pantry"])


def read_pantry(session: Session, user_id: str) -> list[PantryItemResponse]:
    """The user's pantry, sorted by display name."""
    rows = session.execute(
        select(PantryItem.ingredient_id, Ingredient.display_name, PantryItem.added_at)
        .join(Ingredient, Ingredient.id == PantryItem.ingredient_id)
        .where(PantryItem.user_id == user_id)
        .order_by(Ingredient.display_name)
    ).all()
    return [
        PantryItemResponse(
            ingredient_id=row.ingredient_id, display_name=row.display_name, added_at=row.added_at
        )
        for row in rows
    ]


@router.get("/pantry")
def get_pantry(session: DbSession, user_id: CurrentUser) -> list[PantryItemResponse]:
    return read_pantry(session, user_id)


@router.post("/pantry/items")
def add_pantry_items(
    payload: AddPantryItemsRequest,
    session: DbSession,
    user_id: CurrentUser,
) -> list[PantryItemResponse]:
    """Add ingredients to the pantry and return the updated pantry.

    Only catalog ingredients may be added (spec section 4), so unknown ids are rejected
    rather than stored. Ids already in the pantry are ignored.
    """
    requested = list(dict.fromkeys(payload.ingredient_ids))
    known = set(session.scalars(select(Ingredient.id).where(Ingredient.id.in_(requested))).all())
    unknown = [ingredient_id for ingredient_id in requested if ingredient_id not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Unknown ingredient ids", "unknown_ingredient_ids": unknown},
        )

    session.execute(
        insert(PantryItem)
        .values([{"user_id": user_id, "ingredient_id": i} for i in requested])
        .on_conflict_do_nothing()
    )
    session.commit()
    return read_pantry(session, user_id)


@router.delete("/pantry/items/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_pantry_item(ingredient_id: int, session: DbSession, user_id: CurrentUser) -> None:
    """Remove one ingredient. Idempotent: removing what isn't there still returns 204."""
    session.execute(
        delete(PantryItem).where(
            PantryItem.user_id == user_id, PantryItem.ingredient_id == ingredient_id
        )
    )
    session.commit()
