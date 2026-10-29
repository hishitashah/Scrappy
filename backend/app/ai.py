"""The one place Scrappy talks to a model (F7, spec 10.11).

Two things live here, deliberately separated:

- `SubstitutionClient`, the shape the rest of the app depends on. It takes a recipe title,
  what's missing and what's in the pantry, and returns suggestions plus the token counts
  the call used.
- `AnthropicSubstitutions`, the only implementation that reaches the network.

The split is what lets every endpoint test run without an API key, without a network call
and without spending anything: tests supply their own `SubstitutionClient`. The adapter has
its own tests against a stub SDK object, so its parsing is still covered.

**The model is asked for judgment, never for facts** (spec section 4). "What could stand in
for buttermilk?" is a question a model answers well. Which ingredients the user owns, which
are missing, and how many a recipe needs are all counted in SQL, and the answer is checked
against that count afterwards — the model does not get to tell us what we asked.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel, Field

from app.settings import Settings, get_settings

logger = logging.getLogger("scrappy")

# Thinking cannot be disabled on Claude Opus 5.5 and its tokens count toward max_tokens,
# so this ceiling has to leave room for reasoning as well as the answer. `effort: "low"` is
# what keeps the spend down instead of a tight ceiling (spec 10.11).
MAX_TOKENS = 4096
EFFORT = "low"


@dataclass(frozen=True)
class Suggestion:
    """One substitution, exactly as the model proposed it."""

    missing_ingredient: str
    suggestion: str
    reason: str


@dataclass(frozen=True)
class AiResult:
    """Suggestions plus what they cost, in tokens, from the response's own `usage`."""

    suggestions: list[Suggestion]
    input_tokens: int
    output_tokens: int


class AiUnavailable(Exception):
    """The model answered, but not usably. The router turns this into a 502.

    Raised for a response that fails the schema, one the model declined, and one cut off
    at `max_tokens`. All three mean the same thing to a user: no answer this time. A
    half-list of substitutions would be worse than none, because the missing half looks
    like "nothing substitutes for this".

    It carries the token counts anyway, because an unusable answer was still billed. A
    ledger that only counted the answers we liked would understate the real bill, and the
    monthly cap reads that ledger.
    """

    def __init__(self, message: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class SubstitutionClient(Protocol):
    """The seam. Tests replace this; nothing else in the app knows about Anthropic."""

    def suggest(
        self, *, recipe_title: str, missing: Sequence[str], pantry: Sequence[str]
    ) -> AiResult: ...


class _SubstitutionItem(BaseModel):
    """One item of the structured output the model is constrained to return."""

    missing_ingredient: str = Field(description="The missing ingredient, copied exactly")
    suggestion: str = Field(description="What to use instead")
    reason: str = Field(description="Why it works, at most 15 words")


class _SubstitutionList(BaseModel):
    substitutions: list[_SubstitutionItem]


def build_prompt(recipe_title: str, missing: Sequence[str], pantry: Sequence[str]) -> str:
    """Ask for one substitution per missing ingredient, and permit silence.

    The permission to skip matters: without it a model asked for N suggestions will invent
    an Nth. "Nothing really substitutes for yeast" is a more useful answer than a bad
    substitute, and the panel simply shows one fewer row.
    """
    pantry_list = ", ".join(pantry) if pantry else "nothing"
    return (
        f"A cook is making {recipe_title} and is missing some ingredients.\n\n"
        f"Missing: {', '.join(missing)}\n"
        f"Already in their kitchen: {pantry_list}\n\n"
        "Suggest at most one substitution for each missing ingredient. Prefer something "
        "they already have. Keep each reason to 15 words or fewer. If an ingredient has no "
        "sensible substitute, leave it out rather than suggesting something that would not "
        "work."
    )


class AnthropicSubstitutions:
    """Calls Claude, with structured outputs so the reply can't be prose.

    The client is injected rather than built here, which is what makes the adapter itself
    testable: its tests pass a stub with the same `messages.parse` surface.
    """

    def __init__(self, client: object, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def suggest(
        self, *, recipe_title: str, missing: Sequence[str], pantry: Sequence[str]
    ) -> AiResult:
        # Imported here, not at module level, so a deployment with AI switched off never
        # loads the SDK at all. `APIError` is the base class of every failure the SDK
        # raises: a rejected key, a rate limit, a timeout, a dropped connection.
        from anthropic import APIError

        try:
            response = self._client.messages.parse(  # type: ignore[attr-defined]
                model=self._settings.ai_model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": EFFORT},
                output_format=_SubstitutionList,
                messages=[{"role": "user", "content": build_prompt(recipe_title, missing, pantry)}],
            )
        except APIError as failure:
            # No token counts: a request that was rejected or never answered was not
            # billed, and the ledger must never invent spend it cannot see. Without this
            # branch the error reaches the handler in observability.py and becomes a 500,
            # which reads as a Scrappy bug rather than "the model is unreachable".
            logger.warning("ai call failed", extra={"reason": type(failure).__name__})
            raise AiUnavailable(f"anthropic call failed: {type(failure).__name__}") from failure

        # Checked before the content is read, because both of these leave `parsed_output`
        # empty or partial. `refusal` is a safety decline; `max_tokens` means truncated.
        if response.stop_reason in ("refusal", "max_tokens"):
            logger.warning("ai call unusable", extra={"reason": response.stop_reason})
            raise AiUnavailable(
                f"model stopped with {response.stop_reason}",
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

        parsed = response.parsed_output
        if parsed is None:
            logger.warning("ai call unusable", extra={"reason": "no_parsed_output"})
            raise AiUnavailable(
                "model returned no structured output",
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

        return AiResult(
            suggestions=[
                Suggestion(
                    missing_ingredient=item.missing_ingredient,
                    suggestion=item.suggestion,
                    reason=item.reason,
                )
                for item in parsed.substitutions
            ],
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


@lru_cache
def _anthropic_client(api_key: str) -> object:
    """One SDK client per process, built on first use.

    Imported inside the function so that a deployment with AI switched off never imports
    the SDK at all, and so tests that replace the seam don't need it either.
    """
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def get_substitution_client() -> SubstitutionClient | None:
    """FastAPI dependency. Tests override it; production gets the real thing.

    Returns None rather than raising when there is no key, because a dependency that
    raises runs *before* the handler, and the handler is where the kill switch lives: a
    deployment with AI switched off and no key yet must answer 503, not 500.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return AnthropicSubstitutions(_anthropic_client(settings.anthropic_api_key), settings)
