"""Who is calling? (spec 10.4)

`get_current_user` is a dependency on every router except /health. It has two modes:

- shared:  every caller is the same fixed user. Used locally before Cognito exists, and
           briefly on the live site between the first deploy (M4) and login (M5).
- cognito: the bearer token is verified against the Cognito user pool. Arrives in M5.

Either way the user row is upserted, because pantry rows reference `users.id`.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.settings import Settings, get_settings

SHARED_USER_ID = "shared-user"


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Return the caller's user id, creating the user row on first sight."""
    if settings.auth_mode == "cognito":
        # M5 replaces this with PyJWT verification of the Cognito access token.
        raise NotImplementedError("AUTH_MODE=cognito is implemented in M5")

    user_id = SHARED_USER_ID
    session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
    session.commit()
    return user_id


CurrentUser = Annotated[str, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_session)]
