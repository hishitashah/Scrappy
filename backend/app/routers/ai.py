"""POST /recipes/{id}/substitutions — AI substitutions (F7, spec 10.11).

The only endpoint in Scrappy that can spend money, so the order of operations below is the
feature's whole safety story:

1. `AI_ENABLED` — an operator pause means paused, before anything else happens.
2. Nothing missing — answer `[]` without asking a model what to substitute for nothing.
3. The cache — an answer already paid for, which costs nothing and counts nothing.
4. The monthly cap, then the caller's daily count.
5. Only then, the call.

Steps 2 and 3 are the ones that actually keep the bill small in normal use; steps 1, 4 and
5 are what make a worst case survivable.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import AiUnavailable, SubstitutionClient, get_substitution_client
from app.auth import CurrentUser, DbSession
from app.models import Ingredient, PantryItem, RecipeIngredient
from app.normalize import normalize
from app.routers.recipes import _visible_recipe
from app.schemas import SubstitutionResponse, SubstitutionsResponse
from app.settings import Settings, get_settings
from app.staples import staple_ingredient_ids
from app.usage import (
    SUBSTITUTIONS,
    Allowance,
    cached_payload,
    check_allowance,
    pantry_hash,
    record_call,
    store_payload,
)

logger = logging.getLogger("scrappy")

router = APIRouter(tags=["ai"])

AppSettings = Annotated[Settings, Depends(get_settings)]
AiClient = Annotated[SubstitutionClient | None, Depends(get_substitution_client)]

PAUSED = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="AI features are paused",
)


def _in_pantry_ids(session: Session, suggestions: list[str]) -> dict[str, int]:
    """Map each suggested name to a catalog ingredient id, where one exists.

    The model writes "plain yogurt"; the catalog holds "yogurt". `normalize` is the same
    function the import and the pantry use, so a suggestion is matched the way a typed
    ingredient would be — including its aliases.
    """
    wanted = {normalize(name): name for name in suggestions}
    if not wanted:
        return {}

    rows = session.execute(
        select(Ingredient.id, Ingredient.name, Ingredient.aliases).where(
            or_(
                Ingredient.name.in_(wanted),
                Ingredient.aliases.overlap(list(wanted)),
            )
        )
    ).all()

    found: dict[str, int] = {}
    for row in rows:
        for key in (row.name, *row.aliases):
            if key in wanted:
                found[wanted[key]] = row.id
    return found


@router.post("/recipes/{recipe_id}/substitutions")
def suggest_substitutions(
    recipe_id: int,
    session: DbSession,
    user_id: CurrentUser,
    settings: AppSettings,
    client: AiClient,
) -> SubstitutionsResponse:
    """Suggest a stand-in for each of this recipe's missing ingredients."""
    if not settings.ai_enabled:
        raise PAUSED

    recipe = _visible_recipe(session, recipe_id, user_id)

    pantry_rows = session.execute(
        select(Ingredient.id, Ingredient.display_name)
        .join(PantryItem, PantryItem.ingredient_id == Ingredient.id)
        .where(PantryItem.user_id == user_id)
        .order_by(Ingredient.display_name)
    ).all()
    pantry_ids = {row.id for row in pantry_rows}
    # Water is assumed owned, exactly as the recipe page treats it (spec section 4).
    owned_ids = pantry_ids | set(staple_ingredient_ids(session))

    rows = session.execute(
        select(Ingredient.id, Ingredient.display_name)
        .join(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.id)
        .where(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.position)
    ).all()

    missing = [row.display_name for row in rows if row.id not in owned_ids]
    # The whole pantry, not just this recipe's share of it: the point of asking is to be
    # told about something the cook already has, which may be nowhere in the recipe.
    pantry = [row.display_name for row in pantry_rows]

    # Nothing to substitute: a free, honest answer (spec 10.11).
    if not missing:
        return SubstitutionsResponse(suggestions=[])

    # Keyed on the real pantry, which is what the question depends on.
    key = pantry_hash(sorted(pantry_ids))

    cached = cached_payload(session, recipe.id, key)
    if cached is not None:
        return SubstitutionsResponse(suggestions=[SubstitutionResponse(**item) for item in cached])

    allowance = check_allowance(session, user_id, SUBSTITUTIONS, settings)
    if allowance is Allowance.MONTHLY_CAP:
        raise PAUSED
    if allowance is Allowance.DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily substitution limit reached",
        )
    if client is None:
        # Enabled but unkeyed. Settings validation refuses this at startup, so reaching
        # here means something is misconfigured — a pause is the safe answer either way.
        logger.error("ai enabled with no client available")
        raise PAUSED

    try:
        result = client.suggest(recipe_title=recipe.title, missing=missing, pantry=pantry)
    except AiUnavailable as unusable:
        # Billed all the same, so the ledger has to see it: a refused or truncated answer
        # that cost money and recorded nothing would leave the monthly cap understating
        # real spend, which is the one thing the cap must never do.
        if unusable.input_tokens or unusable.output_tokens:
            record_call(
                session,
                user_id,
                SUBSTITUTIONS,
                unusable.input_tokens,
                unusable.output_tokens,
                settings,
            )
            session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model did not return a usable answer",
        ) from None

    # The call is paid for whatever it returned, so it is recorded before the answer is
    # judged. Charging only for answers we liked would understate the real bill.
    record_call(
        session,
        user_id,
        SUBSTITUTIONS,
        result.input_tokens,
        result.output_tokens,
        settings,
    )

    # What we asked about is ours to decide: a suggestion for an ingredient that isn't
    # missing is dropped rather than shown (spec section 4).
    by_display = {name.casefold(): name for name in missing}
    kept = [
        suggestion
        for suggestion in result.suggestions
        if suggestion.missing_ingredient.casefold() in by_display
    ]

    catalog_ids = _in_pantry_ids(session, [suggestion.suggestion for suggestion in kept])
    payload: list[dict[str, object]] = [
        {
            "missing_ingredient": by_display[suggestion.missing_ingredient.casefold()],
            "suggestion": suggestion.suggestion,
            "reason": suggestion.reason,
            "in_pantry": catalog_ids.get(suggestion.suggestion) in owned_ids,
        }
        for suggestion in kept
    ]

    store_payload(session, recipe.id, key, payload)
    # Without this the whole transaction is discarded when the session closes: the money
    # would be spent, the ledger would read zero, and the cache would never hit.
    session.commit()

    return SubstitutionsResponse(suggestions=[SubstitutionResponse(**item) for item in payload])
