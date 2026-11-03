"""Cleaning a recipe's method, wherever it came from (spec 10.3, 10.12).

The UI numbers steps itself — the recipe page renders an `<ol>` — so numbering carried in
the data is numbering shown twice: "1. 1. Place the chicken in a pot."

Both sources produce it. TheMealDB numbers inconsistently, some recipes putting the number
on its own line and others prefixing the text. A model asked for a method writes "1." at
the start of each step whatever the prompt says, which is why the prompt asking for
unnumbered steps is not enough on its own: this is the part that holds.

Lives in `app/` rather than in the importer because `scripts/` can import from the app and
not the other way round — the same arrangement `catalog.py` has with `upsert_ingredients`.
"""

import re
from collections.abc import Iterable

# A line that is only a number: a heading for the step below it, not a step.
_BARE_NUMBER = re.compile(r"^\d+\s*[.):\-]?$")
# A prefix only counts as numbering when punctuation and whitespace follow, so a step that
# genuinely opens with a quantity ("2 eggs, beaten") keeps its number.
_NUMBER_PREFIX = re.compile(r"^\d+\s*[.):\-]\s+")


def clean_steps(steps: Iterable[str]) -> list[str]:
    """Drop blanks and bare numbers, and strip a leading "3." from each remaining step."""
    cleaned: list[str] = []
    for raw in steps:
        step = raw.strip()
        if not step or _BARE_NUMBER.match(step):
            continue
        step = _NUMBER_PREFIX.sub("", step).strip()
        if step:
            cleaned.append(step)
    return cleaned
