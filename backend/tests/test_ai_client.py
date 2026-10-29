"""The Anthropic adapter itself (spec 10.11).

`test_ai_substitutions.py` replaces the whole client, which leaves the adapter's own
parsing untested. These tests fill that gap with a stub standing in for the SDK: same
`messages.parse` surface, no network, no key, no spend. What they cover is the part that
only ever runs against a real response — reading `usage`, and refusing the three kinds of
answer that look like success but aren't.
"""

from types import SimpleNamespace

import pytest

from app.ai import (
    EFFORT,
    MAX_TOKENS,
    AiUnavailable,
    AnthropicSubstitutions,
    build_prompt,
    get_substitution_client,
)
from app.settings import Settings


def settings() -> Settings:
    return Settings(_env_file=None, env="test", ai_model="claude-opus-5-5")


class StubMessages:
    """Records the request and returns whatever response the test scripted."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return self.response


def stub_client(response: object) -> SimpleNamespace:
    return SimpleNamespace(messages=StubMessages(response))


def answer(*items: tuple[str, str, str], stop_reason: str = "end_turn") -> SimpleNamespace:
    """A response shaped like the SDK's, carrying the given suggestions."""
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=SimpleNamespace(
            substitutions=[
                SimpleNamespace(missing_ingredient=missing, suggestion=suggestion, reason=reason)
                for missing, suggestion, reason in items
            ]
        ),
        usage=SimpleNamespace(input_tokens=612, output_tokens=308),
    )


def test_a_good_response_becomes_suggestions_and_token_counts() -> None:
    client = stub_client(answer(("Buttermilk", "Milk and lemon juice", "Curdles the same way.")))

    result = AnthropicSubstitutions(client, settings()).suggest(
        recipe_title="Soda Bread", missing=["Buttermilk"], pantry=["Milk", "Lemon"]
    )

    assert [(s.missing_ingredient, s.suggestion) for s in result.suggestions] == [
        ("Buttermilk", "Milk and lemon juice")
    ]
    # Taken from the response, never estimated: the ledger has to hold the real numbers.
    assert (result.input_tokens, result.output_tokens) == (612, 308)


def test_the_request_pins_the_model_the_ceiling_and_the_effort() -> None:
    client = stub_client(answer())

    AnthropicSubstitutions(client, settings()).suggest(
        recipe_title="Soda Bread", missing=["Buttermilk"], pantry=[]
    )

    sent = client.messages.kwargs
    assert sent["model"] == "claude-opus-5-5"
    assert sent["max_tokens"] == MAX_TOKENS
    # Effort is the cost control, since thinking can't be switched off on this model.
    assert sent["output_config"] == {"effort": EFFORT}
    # Structured output: the reply is a validated object, not prose to be parsed.
    assert sent["output_format"].__name__ == "_SubstitutionList"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_a_declined_or_truncated_answer_is_refused(stop_reason: str) -> None:
    """Both look like a 200 and neither is usable.

    A truncated list is the dangerous one: the suggestions that didn't fit would read as
    "nothing substitutes for these", which is a wrong answer rather than a missing one.
    """
    client = stub_client(answer(("Oil", "Butter", "Both carry heat."), stop_reason=stop_reason))

    with pytest.raises(AiUnavailable) as raised:
        AnthropicSubstitutions(client, settings()).suggest(
            recipe_title="Egg fried rice", missing=["Oil"], pantry=[]
        )

    # The tokens travel with the failure, because the call was billed regardless.
    assert (raised.value.input_tokens, raised.value.output_tokens) == (612, 308)


def test_a_response_with_no_structured_output_is_refused() -> None:
    client = stub_client(
        SimpleNamespace(
            stop_reason="end_turn",
            parsed_output=None,
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
    )

    with pytest.raises(AiUnavailable):
        AnthropicSubstitutions(client, settings()).suggest(
            recipe_title="Egg fried rice", missing=["Oil"], pantry=[]
        )


def test_the_prompt_names_the_recipe_the_gaps_and_the_pantry() -> None:
    prompt = build_prompt("Egg fried rice", ["Oil", "Soy Sauce"], ["Rice", "Egg"])

    assert "Egg fried rice" in prompt
    assert "Oil, Soy Sauce" in prompt
    assert "Rice, Egg" in prompt
    # The permission to say nothing: without it, a model asked for two suggestions invents
    # a second one rather than admitting there isn't a good substitute.
    assert "no sensible substitute" in prompt


def test_an_empty_pantry_reads_as_nothing_rather_than_a_blank() -> None:
    assert "Already in their kitchen: nothing" in build_prompt("Boiled egg", ["Egg"], [])


def test_there_is_no_client_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing key yields None, not an exception.

    The router's kill-switch check has to run first, so the honest answer for a deployment
    with AI switched off and no key yet is 503 — which a raising dependency would turn
    into a 500.
    """
    monkeypatch.setattr("app.ai.get_settings", lambda: settings())

    assert get_substitution_client() is None
