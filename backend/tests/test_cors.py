"""The CORS allowlist is duplicated, so something has to check it (spec 10.7).

`app.main.CORS_METHODS` is the list the local middleware uses; `infra/api.tf` repeats it
on the Lambda Function URL, which is what serves CORS in production. They are separate
because Terraform cannot import Python — but two copies of a list drift.

A method missing from either copy fails in a way no endpoint test can see. The route
exists, the handler is correct, and `TestClient` is happy, because it never performs a
preflight. A real browser does: it sends `OPTIONS`, gets back an `Allow-Methods` without
the method it asked about, and refuses to send the request at all. The feature does
nothing, and the server log stays empty because nothing ever reached it.

That is exactly how `PATCH /me` shipped broken in M8 — the app's first PATCH endpoint,
added without either allowlist being touched. So these tests derive the methods from the
routes themselves rather than trusting a hand-kept list.
"""

import re
from pathlib import Path

from app.main import CORS_METHODS, app

API_TF = Path(__file__).resolve().parents[2] / "infra" / "api.tf"

# Matches the `allow_methods = [...]` line inside the Function URL's `cors` block.
_ALLOW_METHODS = re.compile(r"^\s*allow_methods\s*=\s*\[([^\]]*)\]", re.MULTILINE)


def _served_methods() -> set[str]:
    """Every method the app actually serves, read from its own OpenAPI schema.

    The schema rather than `app.routes`: this version of FastAPI wraps included routers,
    so the route objects are not all reachable by iterating the top-level list.
    """
    methods: set[str] = set()
    for operations in app.openapi()["paths"].values():
        methods.update(method.upper() for method in operations)
    return methods


def test_every_served_method_is_allowed() -> None:
    """The check that would have caught M8: a new method, no allowlist entry."""
    missing = _served_methods() - set(CORS_METHODS)

    assert not missing, (
        f"the API serves {sorted(missing)} but CORS does not allow it — "
        "a browser's preflight will block it and the request will never be sent"
    )


def test_the_terraform_cors_block_exists() -> None:
    """A missing file or renamed block would make the comparison below vacuous."""
    assert API_TF.is_file(), f"expected the Function URL's CORS block at {API_TF}"
    assert _ALLOW_METHODS.search(API_TF.read_text(encoding="utf-8")), (
        "found no `allow_methods = [...]` — has the cors block moved?"
    )


def test_production_allows_exactly_what_the_app_allows() -> None:
    """Production CORS is the Function URL's, not the middleware's, so it has to agree.

    Membership, not order: unlike the store picker, nothing here is displayed in order.
    """
    found = _ALLOW_METHODS.search(API_TF.read_text(encoding="utf-8"))
    assert found
    declared = {method.strip().strip('"') for method in found.group(1).split(",") if method.strip()}

    assert declared == set(CORS_METHODS), (
        f"infra/api.tf allows {sorted(declared)} but the app expects {sorted(CORS_METHODS)}"
    )
