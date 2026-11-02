"""The supermarket chains a user can pick from (F9, spec 10.13).

Keys only. The search URL for each chain lives in `frontend/src/lib/stores.ts`, because
the link is built and followed by the browser — Scrappy's server never contacts a
retailer, and F9 adds no third-party call to the running app (spec section 4).

**Mirrored file.** Adding or removing a chain means editing this set *and* the table in
`frontend/src/lib/stores.ts`. `test_stores.py` reads that file and fails if the two
disagree, so a half-done change is caught rather than shipped.
"""

from typing import Literal, get_args

# The chain keys from spec 10.13, in the order the picker shows them. A Literal rather
# than a plain tuple so that a request model can use it directly: the allowed values then
# reach /openapi.json, and a bad key is a 422 before any handler runs.
StoreKey = Literal[
    "walmart",
    "target",
    "kroger",
    "heb",
    "publix",
    "safeway",
    "whole-foods",
]

STORE_KEYS: tuple[str, ...] = get_args(StoreKey)
