"""Who is calling? (spec 10.4)

`get_current_user` is a dependency on every router except /health. It has two modes:

- cognito: the bearer token is verified against the Cognito user pool.
- shared:  every caller is the same fixed user. Used before Cognito existed, and briefly on
           the live site between the first deploy (M4) and login (M5).

Either way the user row is upserted, because pantry rows reference `users.id`.

Scrappy never sees a password: Cognito holds the directory, and this file only checks that a
token was signed by it, is still valid, and was issued for this app.
"""

import logging
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.settings import Settings, get_settings

logger = logging.getLogger("scrappy")

SHARED_USER_ID = "shared-user"

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@lru_cache
def _jwk_client(jwks_url: str) -> PyJWKClient:
    """One key client per process.

    Cached because each Lambda instance should fetch Cognito's public keys once, on its cold
    start, and not on every request. Verification itself is then local arithmetic: no network
    call, no dependency on Cognito being reachable.
    """
    return PyJWKClient(jwks_url, cache_keys=True)


def _verify_cognito_token(token: str, settings: Settings) -> str:
    """Return the `sub` of a valid access token, or raise 401.

    Checks the signature, expiry, issuer, audience and token type. Errors deliberately say
    what failed in the log but never echo the token.
    """
    try:
        signing_key = _jwk_client(settings.cognito_jwks_url).get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={"require": ["exp", "sub", "token_use", "client_id"]},
        )
    except jwt.PyJWTError as error:
        logger.warning("token rejected", extra={"reason": type(error).__name__})
        raise UNAUTHORIZED from error

    # Cognito issues an access token and an ID token from the same pool, signed by the same
    # key. The ID token describes the user to the client; it is not authorization for an API,
    # and accepting one here is a well-known mistake.
    if claims.get("token_use") != "access":
        logger.warning("token rejected", extra={"reason": "token_use is not access"})
        raise UNAUTHORIZED

    # Access tokens carry the app client in `client_id` rather than `aud`, so this is checked
    # by hand: a token minted for a different client of the same pool must not work here.
    if claims.get("client_id") != settings.cognito_client_id:
        logger.warning("token rejected", extra={"reason": "client_id mismatch"})
        raise UNAUTHORIZED

    return str(claims["sub"])


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UNAUTHORIZED
    return token


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Return the caller's user id, creating the user row on first sight."""
    if settings.auth_mode == "cognito":
        user_id = _verify_cognito_token(_bearer_token(request), settings)
    else:
        user_id = SHARED_USER_ID

    # The id is opaque — a Cognito `sub` — so no personal data reaches this database.
    session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
    session.commit()
    # The request log line is written by middleware, outside the dependency, so hand the
    # user over on request.state rather than trying to thread it through (spec 10.9).
    request.state.user_id = user_id
    return user_id


CurrentUser = Annotated[str, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_session)]
