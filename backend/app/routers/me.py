"""The caller's own settings (spec 10.13).

One field so far: which supermarket the grocery list should link to. It lives on the
server rather than in the browser so that a user's choice follows them between devices,
like their pantry does.
"""

from fastapi import APIRouter

from app.auth import CurrentUser, DbSession
from app.models import User
from app.schemas import MeResponse, UpdateMeRequest

router = APIRouter(tags=["me"])


@router.get("/me")
def get_me(session: DbSession, user_id: CurrentUser) -> MeResponse:
    """The caller's settings. The row always exists: auth creates it on first sight."""
    user = session.get(User, user_id)
    return MeResponse(preferred_store=user.preferred_store if user else None)


@router.patch("/me")
def update_me(
    payload: UpdateMeRequest,
    session: DbSession,
    user_id: CurrentUser,
) -> MeResponse:
    """Set or clear the preferred store.

    The key is validated by `UpdateMeRequest`, so an unknown chain is a 422 that appears
    in `/openapi.json` rather than a check buried in here. Null is allowed and means
    "unset", which the list renders as "Pick a store".
    """
    user = session.get(User, user_id)
    if user is not None:
        user.preferred_store = payload.preferred_store
        session.commit()
    return MeResponse(preferred_store=payload.preferred_store)
