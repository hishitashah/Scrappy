"""The two endpoints that can spend money (F7 and F8, spec 10.11 and 10.12).

Both live here rather than in separate files, because the order of operations below is the
features' whole safety story and it is worth being able to read it in one place:

1. `AI_ENABLED` — an operator pause means paused, before anything else happens.
2. A free, honest answer where one exists — nothing missing to substitute for, or an empty
   pantry to cook from — without asking a model.
3. The cache, for substitutions: an answer already paid for costs nothing and counts
   nothing. Generation has none by design, because pressing the button again means "give
   me a different recipe" (spec 10.12).
4. The monthly cap, then the caller's daily count for that feature.
5. Only then, the call.

Steps 2 and 3 are what keep the bill small in normal use; steps 1, 4 and 5 are what make a
worst case survivable.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.ai import (
    AiUnavailable,
    GenerationClient,
    SubstitutionClient,
    get_generation_client,
    get_substitution_client,
)
from app.auth import CurrentUser, DbSession
from app.catalog import ensure_ingredient_ids, find_ingredient_ids
from app.models import Ingredient, PantryItem, Recipe, RecipeIngredient
from app.routers.recipes import (
    GENERATED,
    _visible_recipe,
    owned_ingredient_ids,
    recipe_ingredients,
)
from app.schemas import RecipeDetailResponse, SubstitutionResponse, SubstitutionsResponse
from app.settings import Settings, get_settings
from app.staples import staple_ingredient_ids
from app.usage import (
    GENERATION,
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
AiGenerator = Annotated[GenerationClient | None, Depends(get_generation_client)]

PAUSED = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="AI features are paused",
)


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

    catalog_ids = find_ingredient_ids(session, [suggestion.suggestion for suggestion in kept])
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


@router.post("/recipes/generate")
def generate_recipe(
    session: DbSession,
    user_id: CurrentUser,
    settings: AppSettings,
    client: AiGenerator,
) -> RecipeDetailResponse:
    """Write a recipe from the caller's pantry and save it to their account (spec 10.12)."""
    if not settings.ai_enabled:
        raise PAUSED

    pantry_rows = session.execute(
        select(Ingredient.id, Ingredient.display_name)
        .join(PantryItem, PantryItem.ingredient_id == Ingredient.id)
        .where(PantryItem.user_id == user_id)
        .order_by(Ingredient.display_name)
    ).all()

    # Nothing to cook from, so nothing to ask. Checked before any guardrail, because a
    # request that can't be answered shouldn't consume today's allowance. Pantry rows
    # only: water is assumed everywhere (spec section 4), but a kitchen holding nothing
    # but water is still empty.
    if not pantry_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Add some ingredients first",
        )

    allowance = check_allowance(session, user_id, GENERATION, settings)
    if allowance is Allowance.MONTHLY_CAP:
        raise PAUSED
    if allowance is Allowance.DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily recipe limit reached",
        )
    if client is None:
        logger.error("ai enabled with no client available")
        raise PAUSED

    pantry = [row.display_name for row in pantry_rows]

    try:
        result = client.generate(pantry=pantry)
    except AiUnavailable as unusable:
        # Billed all the same, so the ledger has to see it (see the F7 handler above).
        if unusable.input_tokens or unusable.output_tokens:
            record_call(
                session,
                user_id,
                GENERATION,
                unusable.input_tokens,
                unusable.output_tokens,
                settings,
            )
            session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model did not return a usable answer",
        ) from None

    record_call(session, user_id, GENERATION, result.input_tokens, result.output_tokens, settings)

    # Every line is saved, including an ingredient the cook doesn't actually have: the
    # prompt asks for the pantry and nothing else, but models add salt anyway. Keeping it
    # means the recipe reports "you have 7 of 8" and the method still makes sense.
    # Dropping it would promise 100% while orphaning "season with salt" in step 3.
    lines = result.recipe.lines
    ingredient_ids = ensure_ingredient_ids(session, [line.display_name for line in lines])

    recipe = Recipe(
        source=GENERATED,
        # Null, so the unique constraint on (source, source_id) doesn't bind: Postgres
        # treats nulls as distinct, and every generated recipe is its own thing.
        source_id=None,
        title=result.recipe.title,
        steps=list(result.recipe.steps),
        created_by=user_id,
    )
    session.add(recipe)
    session.flush()

    # Deduplicated on the way in: (recipe_id, ingredient_id) is the primary key, and two
    # lines of one recipe can normalize to the same ingredient ("Eggs" and "egg").
    seen: set[int] = set()
    for position, line in enumerate(lines):
        # Absent when the name was punctuation or blank, which is no ingredient at all.
        ingredient_id = ingredient_ids.get(line.display_name)
        if ingredient_id is None or ingredient_id in seen:
            continue
        seen.add(ingredient_id)
        session.add(
            RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=ingredient_id,
                measure=line.measure,
                position=position,
            )
        )

    # Money spent, recipe written: both are discarded without this (see the F7 handler).
    session.commit()

    return RecipeDetailResponse(
        id=recipe.id,
        title=recipe.title,
        # A generated recipe has no category, cuisine, photo, video or source, and none are
        # invented: the page shows an "AI-generated" badge where the tags would be.
        category=None,
        area=None,
        image_url=None,
        youtube_url=None,
        source_url=None,
        steps=recipe.steps,
        generated=True,
        ingredients=recipe_ingredients(session, recipe.id, owned_ingredient_ids(session, user_id)),
    )
