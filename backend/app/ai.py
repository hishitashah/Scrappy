"""The one place Scrappy talks to a model (F7 and F8, spec 10.11 and 10.12).

Each feature is a pair, deliberately separated:

- a Protocol — `SubstitutionClient`, `GenerationClient` — which is the shape the rest of
  the app depends on, and returns the token counts the call used along with its answer.
- an adapter — `AnthropicSubstitutions`, `AnthropicGeneration` — the only implementations
  that reach the network.

The split is what lets every endpoint test run without an API key, without a network call
and without spending anything: tests supply their own client. The adapters have their own
tests against a stub SDK object, so their parsing is still covered.

Two features, two Protocols, rather than one client with two methods: each endpoint then
overrides only the dependency it uses, and a test for one can't accidentally satisfy the
other.

**The model is asked for judgment, never for facts** (spec section 4). "What could stand in
for buttermilk?" is a question a model answers well. Which ingredients the user owns, which
are missing, and how many a recipe needs are all counted in SQL, and the answer is checked
against that count afterwards — the model does not get to tell us what we asked.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.settings import Settings, get_settings

logger = logging.getLogger("scrappy")

# Thinking cannot be disabled on Claude Opus 5.5 and its tokens count toward max_tokens,
# so this ceiling has to leave room for reasoning as well as the answer. `effort: "low"` is
# what keeps the spend down instead of a tight ceiling (spec 10.11).
MAX_TOKENS = 4096
# A whole recipe — a title, every ingredient with its measure, and numbered steps — needs
# far more room than two lines of substitution, and the same thinking tokens come out of
# the same ceiling (spec 10.12).
GENERATION_MAX_TOKENS = 8192
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


@dataclass(frozen=True)
class GeneratedLine:
    """One ingredient line of a generated recipe, as the model wrote it."""

    display_name: str
    measure: str | None


@dataclass(frozen=True)
class GeneratedRecipe:
    """A recipe the model wrote. Not yet saved, and not yet mapped onto the catalog."""

    title: str
    lines: list[GeneratedLine]
    steps: list[str]


@dataclass(frozen=True)
class GenerationResult:
    """A generated recipe plus what it cost, in tokens, from the response's own `usage`."""

    recipe: GeneratedRecipe
    input_tokens: int
    output_tokens: int


class SubstitutionClient(Protocol):
    """The seam. Tests replace this; nothing else in the app knows about Anthropic."""

    def suggest(
        self, *, recipe_title: str, missing: Sequence[str], pantry: Sequence[str]
    ) -> AiResult: ...


class GenerationClient(Protocol):
    """The same seam for F8. The pantry is the whole input: there is no recipe yet."""

    def generate(self, *, pantry: Sequence[str]) -> GenerationResult: ...


class _SubstitutionItem(BaseModel):
    """One item of the structured output the model is constrained to return."""

    missing_ingredient: str = Field(description="The missing ingredient, copied exactly")
    suggestion: str = Field(description="What to use instead")
    reason: str = Field(description="Why it works, at most 15 words")


class _SubstitutionList(BaseModel):
    substitutions: list[_SubstitutionItem]


class _GeneratedIngredient(BaseModel):
    """One ingredient line of the structured output the model is constrained to return."""

    name: str = Field(description="The ingredient alone, with no quantity, e.g. 'rice'")
    measure: str | None = Field(description="How much, as written, e.g. '2 cups'")


class _GeneratedRecipe(BaseModel):
    title: str = Field(description="A short dish name, at most 6 words")
    ingredients: list[_GeneratedIngredient]
    steps: list[str] = Field(description="The method, one step per item, in order")


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


def build_generation_prompt(pantry: Sequence[str]) -> str:
    """Ask for a recipe built around this pantry, seasoned from a short list of staples.

    An earlier version asked for the listed ingredients and nothing else. It was honest
    and useless: a pantry of chicken and rice produced boiled chicken and plain rice,
    because that is all "nothing else" permits. Most kitchens hold salt and oil, and a
    cook who typed in two ingredients has not sworn they own only two.

    So the staples below are allowed and anything further is not — the line being a
    shopping trip. Every staple used is still listed as an ingredient, so the recipe
    reports "you have 3 of 6" and the missing rows carry "I have this" (spec 10.11) for
    the salt the cook never typed in. Silently leaving them out would be the bad version:
    step 3 would season with salt that appears nowhere.
    """
    pantry_list = ", ".join(pantry) if pantry else "nothing"
    return (
        f"A cook has these ingredients: {pantry_list}\n\n"
        "Write one recipe built around them. You may also use water and a few basic "
        "pantry staples even if they are not listed — salt, pepper, cooking oil or "
        "butter, and common aromatics such as onion or garlic — because most kitchens "
        "have them. Do not use anything beyond that: no stocks, special sauces, fresh "
        "herbs or other produce, since those would mean a shopping trip. Give the dish a "
        "short name, list every ingredient with how much to use, including any staples "
        "you added, and write the method as a list of steps. Do not number the steps "
        "yourself — the app numbers them. Keep it to something a home cook can follow."
    )


def _parsed_or_raise(response: Any) -> Any:
    """Return the structured output, or refuse the three answers that only look like one.

    `refusal` is a safety decline and `max_tokens` means truncated; both leave
    `parsed_output` empty or partial, so they are checked before the content is read. A
    missing `parsed_output` on an otherwise normal stop is the third.

    Truncation is the dangerous one. Half a list reads as a complete answer — "nothing
    substitutes for these", or a recipe whose method stops mid-step — which is a wrong
    answer rather than a missing one.

    The token counts travel with the failure because the call was billed regardless.
    """
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
    return parsed


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

        parsed = _parsed_or_raise(response)
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


class AnthropicGeneration:
    """Calls Claude for a whole recipe. Same seam, same failure handling as F7."""

    def __init__(self, client: object, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def generate(self, *, pantry: Sequence[str]) -> GenerationResult:
        from anthropic import APIError

        try:
            response = self._client.messages.parse(  # type: ignore[attr-defined]
                model=self._settings.ai_model,
                max_tokens=GENERATION_MAX_TOKENS,
                output_config={"effort": EFFORT},
                output_format=_GeneratedRecipe,
                messages=[{"role": "user", "content": build_generation_prompt(pantry)}],
            )
        except APIError as failure:
            logger.warning("ai call failed", extra={"reason": type(failure).__name__})
            raise AiUnavailable(f"anthropic call failed: {type(failure).__name__}") from failure

        parsed = _parsed_or_raise(response)
        return GenerationResult(
            recipe=GeneratedRecipe(
                title=parsed.title,
                lines=[
                    GeneratedLine(display_name=item.name, measure=item.measure)
                    for item in parsed.ingredients
                ],
                steps=list(parsed.steps),
            ),
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


def get_generation_client() -> GenerationClient | None:
    """FastAPI dependency for F8, None when unkeyed, for the reason given above."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return AnthropicGeneration(_anthropic_client(settings.anthropic_api_key), settings)
