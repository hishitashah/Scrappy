"""GET /matches — recipes ranked by how much of each the user can already make (spec 10.2)."""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.auth import CurrentUser, DbSession
from app.matching import find_matches
from app.models import PantryItem
from app.schemas import MatchResponse

router = APIRouter(tags=["matches"])


@router.get("/matches")
def get_matches(
    session: DbSession,
    user_id: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[MatchResponse]:
    """Rank recipes against the caller's saved pantry.

    The client sends no ingredient list: the pantry is read on the server (spec section 4).
    An empty pantry returns [] without querying, and so does a pantry that overlaps nothing.
    """
    ingredient_ids = session.scalars(
        select(PantryItem.ingredient_id).where(PantryItem.user_id == user_id)
    ).all()
    matches = find_matches(session, ingredient_ids, user_id, limit)
    return [MatchResponse.model_validate(match) for match in matches]
