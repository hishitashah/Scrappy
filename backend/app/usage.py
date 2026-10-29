"""AI spend accounting and the guardrails in front of it (spec 14).

Scrappy's AI features are the only thing in the project that costs money, so the money is
tracked here rather than inside the feature code: one place to read, one place to test, and
no way for a new endpoint to start spending without going through it.

Three of the six guardrails live in this file. `AI_ENABLED` is an operator pause,
`AI_MONTHLY_BUDGET_CENTS` is the $5 cap, and the per-user daily limits keep one account
from using the whole month in an afternoon. The cache belongs here too, because an answer
already paid for is the cheapest guardrail there is.

Nothing in this module raises HTTP errors or reads request state: it answers questions
about the ledger, and the router decides what status code that deserves.
"""

import hashlib
import math
from collections.abc import Sequence
from datetime import UTC, date, datetime
from enum import Enum

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AiUserDailyUsage, SubstitutionCache
from app.settings import Settings

# The two values `ai_user_daily_usage.feature` can hold.
SUBSTITUTIONS = "substitutions"
GENERATION = "generation"


class Allowance(Enum):
    """Whether a call may be made, and if not, why not.

    The router maps these to status codes: 503 for both kinds of stop (the feature is off,
    or the month's money is gone) and 429 for a limit that resets tomorrow.
    """

    OK = "ok"
    DISABLED = "disabled"
    MONTHLY_CAP = "monthly_cap"
    DAILY_LIMIT = "daily_limit"


def utc_month(now: datetime | None = None) -> str:
    """The `ai_monthly_usage` key, e.g. "2026-11". UTC, because Lambda runs UTC."""
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def utc_day(now: datetime | None = None) -> date:
    """The `ai_user_daily_usage` key. UTC, for the same reason."""
    return (now or datetime.now(UTC)).date()


def pantry_hash(ingredient_ids: Sequence[int]) -> str:
    """A stable fingerprint of a pantry, for the cache key.

    Sorted first, so the same pantry entered in a different order is the same question.
    """
    joined = ",".join(str(ingredient_id) for ingredient_id in sorted(set(ingredient_ids)))
    return hashlib.sha256(joined.encode()).hexdigest()


def cost_cents(input_tokens: int, output_tokens: int, settings: Settings) -> int:
    """What a call with these token counts costs, rounded up to whole cents.

    Used for reporting a single call. The ledger does not add these up — see
    `record_call`.
    """
    millionths = (
        input_tokens * settings.ai_input_cents_per_mtok
        + output_tokens * settings.ai_output_cents_per_mtok
    )
    return math.ceil(millionths / 1_000_000)


def monthly_spend_cents(session: Session, month: str | None = None) -> int:
    """This month's spend so far. Zero when nothing has been spent yet."""
    spent = session.execute(
        text("SELECT cost_cents FROM ai_monthly_usage WHERE month = :month"),
        {"month": month or utc_month()},
    ).scalar()
    return int(spent or 0)


def daily_calls(session: Session, user_id: str, feature: str, day: date | None = None) -> int:
    """How many calls this user has made for this feature today."""
    calls = session.scalar(
        select(AiUserDailyUsage.calls).where(
            AiUserDailyUsage.user_id == user_id,
            AiUserDailyUsage.day == (day or utc_day()),
            AiUserDailyUsage.feature == feature,
        )
    )
    return int(calls or 0)


def check_allowance(
    session: Session,
    user_id: str,
    feature: str,
    settings: Settings,
) -> Allowance:
    """May this user spend money on this feature right now?

    Called only after the cache has missed, so a cached answer is never withheld by a
    spend limit. The kill switch is checked earlier still, by `ai_is_enabled`.
    """
    if monthly_spend_cents(session) >= settings.ai_monthly_budget_cents:
        return Allowance.MONTHLY_CAP

    daily_limit = (
        settings.ai_daily_substitutions_per_user
        if feature == SUBSTITUTIONS
        else settings.ai_daily_generations_per_user
    )
    if daily_calls(session, user_id, feature) >= daily_limit:
        return Allowance.DAILY_LIMIT

    return Allowance.OK


# One statement per write, so a call can never be charged twice or counted twice.
#
# cost_cents is recomputed from the new token totals rather than incremented by this call's
# own cost. One substitution costs about a cent; rounding each call to an integer and
# adding it would lose a tenth of the spend every time, and a sub-cent call would add
# nothing at all. A monthly cap fed by rounded-down pennies could never fire.
# Every bound number is CAST to bigint. Without the casts Postgres infers the narrowest
# type that fits each literal, so 600 tokens times 400 cents-per-million is smallint times
# smallint — and 240,000 overflows smallint before it ever reaches the division. CAST()
# rather than `::bigint`, because SQLAlchemy's text() reads `:name::type` as part of the
# parameter name and never binds it.
_RECORD_MONTH = text("""
INSERT INTO ai_monthly_usage (month, calls, input_tokens, output_tokens, cost_cents)
VALUES (:month, 1, CAST(:input_tokens AS bigint), CAST(:output_tokens AS bigint),
        ceil((  CAST(:input_tokens AS bigint)  * CAST(:in_rate AS bigint)
              + CAST(:output_tokens AS bigint) * CAST(:out_rate AS bigint)) / 1000000.0)::int)
ON CONFLICT (month) DO UPDATE SET
  calls         = ai_monthly_usage.calls + 1,
  input_tokens  = ai_monthly_usage.input_tokens + excluded.input_tokens,
  output_tokens = ai_monthly_usage.output_tokens + excluded.output_tokens,
  cost_cents    = ceil((
      (ai_monthly_usage.input_tokens  + excluded.input_tokens)  * CAST(:in_rate AS bigint)
    + (ai_monthly_usage.output_tokens + excluded.output_tokens) * CAST(:out_rate AS bigint)
  ) / 1000000.0)::int
""")

_RECORD_DAY = text("""
INSERT INTO ai_user_daily_usage (user_id, day, feature, calls)
VALUES (:user_id, :day, :feature, 1)
ON CONFLICT (user_id, day, feature) DO UPDATE SET
  calls = ai_user_daily_usage.calls + 1
""")


def record_call(
    session: Session,
    user_id: str,
    feature: str,
    input_tokens: int,
    output_tokens: int,
    settings: Settings,
) -> None:
    """Write what a completed call actually used, from the response's own `usage`.

    Recorded after the fact rather than estimated beforehand, so the ledger holds real
    numbers: an estimate that drifts from the bill is worse than no estimate.
    """
    session.execute(
        _RECORD_MONTH,
        {
            "month": utc_month(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "in_rate": settings.ai_input_cents_per_mtok,
            "out_rate": settings.ai_output_cents_per_mtok,
        },
    )
    session.execute(
        _RECORD_DAY,
        {"user_id": user_id, "day": utc_day(), "feature": feature},
    )


def cached_payload(session: Session, recipe_id: int, key: str) -> list[dict[str, object]] | None:
    """The stored answer for this recipe and pantry, or None if there isn't one."""
    payload = session.scalar(
        select(SubstitutionCache.payload).where(
            SubstitutionCache.recipe_id == recipe_id,
            SubstitutionCache.pantry_hash == key,
        )
    )
    return payload if payload is not None else None


def store_payload(
    session: Session, recipe_id: int, key: str, payload: list[dict[str, object]]
) -> None:
    """Remember an answer, so the same question is never paid for twice.

    `do_nothing` on conflict: if two requests raced, the row already there is just as
    good, and overwriting it would mean the later one had nothing to show for its spend.
    """
    session.execute(
        insert(SubstitutionCache)
        .values(recipe_id=recipe_id, pantry_hash=key, payload=payload)
        .on_conflict_do_nothing(index_elements=["recipe_id", "pantry_hash"])
    )
