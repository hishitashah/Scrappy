"""Cognito token verification (spec 10.4).

Tokens are signed here with a locally generated RSA key and the key client is patched, so
these tests never call AWS — the same discipline the import and settings tests follow.
"""

import datetime as dt
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth as auth_module
from app.auth import get_current_user
from app.models import User
from app.settings import Settings

POOL_ID = "us-east-1_TESTPOOL"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL_ID}"
SUB = "11111111-2222-3333-4444-555555555555"


def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


# One key for the whole module: generating RSA keys is slow, and a second one is only needed
# for the "signed by the wrong key" case.
SIGNING_KEY = rsa_key()
OTHER_KEY = rsa_key()


def make_token(
    key: rsa.RSAPrivateKey = SIGNING_KEY,
    **overrides: Any,
) -> str:
    now = dt.datetime.now(dt.UTC)
    claims: dict[str, Any] = {
        "sub": SUB,
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": now + dt.timedelta(hours=1),
        "iat": now,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def cognito_settings() -> Settings:
    return Settings(
        env="local",
        auth_mode="cognito",
        cognito_user_pool_id=POOL_ID,
        cognito_client_id=CLIENT_ID,
    )


def request_with(token: str | None, header: str | None = None) -> Request:
    headers = []
    if header is not None:
        headers.append((b"authorization", header.encode()))
    elif token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request({"type": "http", "method": "GET", "path": "/pantry", "headers": headers})


class FakeSigningKey:
    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self.key = key.public_key()


class FakeJwkClient:
    """Stands in for PyJWKClient: no network, and always offers the same public key."""

    def __init__(self, key: rsa.RSAPrivateKey) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        return FakeSigningKey(self._key)


@pytest.fixture(autouse=True)
def patched_keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(auth_module, "_jwk_client", lambda url: FakeJwkClient(SIGNING_KEY))
    yield


def authenticate(session: Session, token: str | None, header: str | None = None) -> str:
    return get_current_user(request_with(token, header), session, cognito_settings())


def test_a_valid_token_identifies_the_user(session: Session) -> None:
    request = request_with(make_token())

    user_id = get_current_user(request, session, cognito_settings())

    assert user_id == SUB
    # The request log reads the user from here (spec 10.9).
    assert request.state.user_id == SUB


def test_a_valid_token_creates_the_user_row_once(session: Session) -> None:
    for _ in range(2):
        authenticate(session, make_token())

    count = session.scalar(select(func.count()).select_from(User).where(User.id == SUB))
    assert count == 1


def test_an_expired_token_is_rejected(session: Session) -> None:
    expired = make_token(exp=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1))

    with pytest.raises(HTTPException) as error:
        authenticate(session, expired)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_a_token_from_another_pool_is_rejected(session: Session) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(session, make_token(iss="https://cognito-idp.us-east-1.amazonaws.com/other"))

    assert error.value.status_code == 401


def test_an_id_token_is_rejected(session: Session) -> None:
    """Cognito signs ID tokens with the same key; they are not API authorization."""
    with pytest.raises(HTTPException) as error:
        authenticate(session, make_token(token_use="id"))

    assert error.value.status_code == 401


def test_a_token_for_another_client_is_rejected(session: Session) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(session, make_token(client_id="some-other-app"))

    assert error.value.status_code == 401


def test_a_token_signed_by_the_wrong_key_is_rejected(session: Session) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(session, make_token(key=OTHER_KEY))

    assert error.value.status_code == 401


def test_a_missing_header_is_rejected(session: Session) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(session, None)

    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "header",
    ["Bearer", "Basic abc123", "token-without-a-scheme", ""],
)
def test_a_malformed_header_is_rejected(session: Session, header: str) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(session, None, header=header)

    assert error.value.status_code == 401


def test_a_token_missing_required_claims_is_rejected(session: Session) -> None:
    """`require` means a token without token_use or client_id never reaches our own checks."""
    now = dt.datetime.now(dt.UTC)
    thin = jwt.encode(
        {"sub": SUB, "iss": ISSUER, "exp": now + dt.timedelta(hours=1)},
        SIGNING_KEY,
        algorithm="RS256",
    )

    with pytest.raises(HTTPException) as error:
        authenticate(session, thin)

    assert error.value.status_code == 401


def test_shared_mode_still_works(session: Session) -> None:
    """The live site runs on shared mode until the frontend sends tokens."""
    request = request_with(None)

    user_id = get_current_user(request, session, Settings(env="local", auth_mode="shared"))

    assert user_id == "shared-user"
