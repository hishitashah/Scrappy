"""The store catalog is duplicated, so something has to check it (spec 10.13).

`app/stores.py` holds the keys the API validates against; `frontend/src/lib/stores.ts`
holds the same keys with a search URL for each. They are separate because the backend
never builds a retailer URL and the frontend never validates one — but two copies of a
list drift, and a key that exists in the picker and not in the API is a 422 the user
cannot explain.

So this test reads the TypeScript file and compares. It is the same arrangement
`staples.py` has with `ingredientFilter.ts`, with the check that file lacks.
"""

import re
from pathlib import Path

from app.stores import STORE_KEYS

STORES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "stores.ts"

# Matches `key: 'walmart',` in the STORES table, in the order they appear.
_KEY = re.compile(r"^\s*(?:\{\s*)?key:\s*'([a-z-]+)'", re.MULTILINE)


def test_the_frontend_store_table_exists() -> None:
    """A missing file would make every assertion below vacuously true."""
    assert STORES_TS.is_file(), f"expected the mirrored store table at {STORES_TS}"


def test_the_two_store_catalogs_hold_the_same_keys_in_the_same_order() -> None:
    """Order matters as well as membership: it is the order the picker offers them in."""
    found = _KEY.findall(STORES_TS.read_text(encoding="utf-8"))

    assert found, "found no `key:` entries — has the shape of STORES changed?"
    assert tuple(found) == STORE_KEYS


def test_every_frontend_chain_has_a_search_url() -> None:
    """A chain in the picker with no URL is a row that links nowhere."""
    source = STORES_TS.read_text(encoding="utf-8")

    for key in STORE_KEYS:
        # The entry's `search:` line follows its `key:` line within the same object.
        entry = re.search(rf"key:\s*'{re.escape(key)}',.*?search:\s*'([^']+)'", source, re.DOTALL)
        assert entry, f"no search URL found for {key}"
        assert "{query}" in entry.group(1), f"{key}'s URL has no query placeholder"
