"""Import TheMealDB's catalog into Postgres (spec 10.5).

Run with: uv run python -m scripts.import_mealdb

This is the only place in Scrappy that talks to a third-party API. The running app
serves every request from our own database, so the import is deliberately separate:
it can be re-run, and re-running it changes nothing.
"""

from __future__ import annotations

import csv
import json
import string
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2 as httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import Ingredient, Recipe, RecipeIngredient
from app.normalize import normalize

BASE_URL = "https://www.themealdb.com/api/json/v1/1"
SOURCE = "themealdb"
# a-z then 0-9: search.php returns every meal whose title starts with that character,
# and TheMealDB has at least one title starting with a digit (spec 10.5).
FIRST_CHARACTERS = string.ascii_lowercase + string.digits
INGREDIENT_SLOTS = range(1, 21)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
REPORT_PATH = Path(__file__).resolve().parent.parent / "import_report.csv"


@dataclass(frozen=True)
class ParsedLine:
    """One ingredient line of a recipe, already normalized."""

    raw_name: str
    name: str  # canonical, from normalize()
    measure: str | None


@dataclass(frozen=True)
class ParsedRecipe:
    source_id: str
    title: str
    category: str | None
    area: str | None
    image_url: str | None
    youtube_url: str | None
    source_url: str | None
    steps: list[str]
    lines: list[ParsedLine]


@dataclass
class ImportSummary:
    recipes: int = 0
    ingredients_created: int = 0
    unmapped: list[tuple[str, str, str]] = field(default_factory=list)  # raw, canonical, recipe


def _clean(value: Any) -> str | None:
    """TheMealDB uses null, "" and " " interchangeably for "no value"."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def split_steps(instructions: str | None) -> list[str]:
    """Split instructions into numbered steps, dropping blanks and "STEP n" prefixes."""
    if not instructions:
        return []
    steps = []
    for line in instructions.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        step = line.strip()
        if not step:
            continue
        lowered = step.lower()
        if lowered.startswith("step"):
            # "STEP 1" alone is a heading; "STEP 1 Heat the oil" keeps the text.
            remainder = step[4:].lstrip(" .:-")
            digits, _, rest = remainder.partition(" ")
            if digits.isdigit():
                step = rest.strip()
                if not step:
                    continue
        steps.append(step)
    return steps


def parse_meal(meal: dict[str, Any]) -> ParsedRecipe:
    """Turn one raw TheMealDB meal into a ParsedRecipe, pairing ingredients with measures."""
    lines: list[ParsedLine] = []
    for slot in INGREDIENT_SLOTS:
        raw_name = _clean(meal.get(f"strIngredient{slot}"))
        if raw_name is None:
            continue
        canonical = normalize(raw_name)
        if not canonical:
            continue
        lines.append(
            ParsedLine(
                raw_name=raw_name, name=canonical, measure=_clean(meal.get(f"strMeasure{slot}"))
            )
        )

    return ParsedRecipe(
        source_id=str(meal["idMeal"]),
        title=str(meal["strMeal"]).strip(),
        category=_clean(meal.get("strCategory")),
        area=_clean(meal.get("strArea")),
        image_url=_clean(meal.get("strMealThumb")),
        youtube_url=_clean(meal.get("strYoutube")),
        source_url=_clean(meal.get("strSource")),
        steps=split_steps(meal.get("strInstructions")),
        lines=dedupe_lines(lines),
    )


def dedupe_lines(lines: Iterable[ParsedLine]) -> list[ParsedLine]:
    """Two lines mapping to one ingredient keep the first position, measures joined by " + "."""
    merged: dict[str, ParsedLine] = {}
    for line in lines:
        existing = merged.get(line.name)
        if existing is None:
            merged[line.name] = line
            continue
        measures = [m for m in (existing.measure, line.measure) if m]
        merged[line.name] = ParsedLine(
            raw_name=existing.raw_name,
            name=existing.name,
            measure=" + ".join(measures) or None,
        )
    return list(merged.values())


def fetch_json(client: httpx.Client, path: str, cache_key: str) -> dict[str, Any]:
    """Fetch one endpoint, caching the response so re-runs don't hit the API again."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    response = client.get(f"{BASE_URL}/{path}")
    response.raise_for_status()
    payload = response.json()
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def fetch_catalog_names(client: httpx.Client) -> list[str]:
    """TheMealDB's own ingredient list: the canonical names the catalog starts from."""
    payload = fetch_json(client, "list.php?i=list", "ingredients")
    return [str(item["strIngredient"]) for item in payload.get("meals") or []]


def fetch_meals(client: httpx.Client) -> Iterator[dict[str, Any]]:
    """Every meal, swept one first character at a time."""
    for character in FIRST_CHARACTERS:
        payload = fetch_json(client, f"search.php?f={character}", f"meals_{character}")
        yield from payload.get("meals") or []


def upsert_ingredients(
    session: Session, names: Sequence[tuple[str, str]], summary: ImportSummary
) -> dict[str, int]:
    """Ensure every (canonical, display) name exists; return canonical name -> id."""
    existing = {
        name: ingredient_id
        for ingredient_id, name in session.execute(select(Ingredient.id, Ingredient.name)).all()
    }
    for canonical, display in names:
        if canonical in existing:
            continue
        ingredient = Ingredient(name=canonical, display_name=display)
        session.add(ingredient)
        session.flush()
        existing[canonical] = ingredient.id
        summary.ingredients_created += 1
    return existing


def import_recipes(
    session: Session,
    recipes: Iterable[ParsedRecipe],
    catalog_names: Iterable[str],
    summary: ImportSummary | None = None,
) -> ImportSummary:
    """Write the catalog. Idempotent: re-running with the same input changes nothing."""
    summary = summary or ImportSummary()

    catalog = [(normalize(name), name) for name in catalog_names]
    catalog = [(canonical, display) for canonical, display in catalog if canonical]
    ingredient_ids = upsert_ingredients(session, catalog, summary)
    known_canonical = set(ingredient_ids)

    for parsed in recipes:
        # Ingredients TheMealDB's own list doesn't contain are added, never dropped.
        new_names = [
            (line.name, line.raw_name) for line in parsed.lines if line.name not in known_canonical
        ]
        if new_names:
            ingredient_ids = upsert_ingredients(session, new_names, summary)
            for canonical, raw in new_names:
                summary.unmapped.append((raw, canonical, parsed.title))
            known_canonical.update(canonical for canonical, _ in new_names)

        recipe = session.scalar(
            select(Recipe).where(Recipe.source == SOURCE, Recipe.source_id == parsed.source_id)
        )
        if recipe is None:
            recipe = Recipe(source=SOURCE, source_id=parsed.source_id, title=parsed.title, steps=[])
            session.add(recipe)

        recipe.title = parsed.title
        recipe.category = parsed.category
        recipe.area = parsed.area
        recipe.image_url = parsed.image_url
        recipe.youtube_url = parsed.youtube_url
        recipe.source_url = parsed.source_url
        recipe.steps = parsed.steps
        session.flush()

        # Replace the ingredient rows outright, so a changed recipe can't keep stale lines.
        session.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe.id).delete()
        for position, line in enumerate(parsed.lines):
            session.add(
                RecipeIngredient(
                    recipe_id=recipe.id,
                    ingredient_id=ingredient_ids[line.name],
                    measure=line.measure,
                    position=position,
                )
            )
        summary.recipes += 1

    return summary


def write_report(summary: ImportSummary, path: Path = REPORT_PATH) -> None:
    """Names not in TheMealDB's ingredient list. The fix is an alias plus a re-run."""
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["raw_name", "canonical_name", "first_seen_in"])
        writer.writerows(summary.unmapped)


def main() -> int:
    with httpx.Client(timeout=30) as client:
        catalog_names = fetch_catalog_names(client)
        meals = list(fetch_meals(client))

    parsed = [parse_meal(meal) for meal in meals]

    # One transaction: either the whole catalog lands or nothing does.
    with Session(get_engine()) as session, session.begin():
        summary = import_recipes(session, parsed, catalog_names)

    write_report(summary)
    print(f"Recipes imported:      {summary.recipes}")
    print(f"Ingredients created:   {summary.ingredients_created}")
    print(f"Unmapped names:        {len(summary.unmapped)} (see {REPORT_PATH.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
