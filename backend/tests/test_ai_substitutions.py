"""POST /recipes/{id}/substitutions (spec 10.11).

The Anthropic client is replaced throughout, so these tests never reach the network and
never spend money. What they actually verify is the accounting around the call: that the
cache works, that each guardrail fires, and that the ledger ends up holding the real token
counts. A feature that can spend money needs its arithmetic tested more than its prompt.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import AiResult, AiUnavailable, Suggestion, get_substitution_client
from app.main import app
from app.models import PantryItem, User
from app.settings import Settings, get_settings
from app.usage import SUBSTITUTIONS, utc_day, utc_month
from tests.conftest import OTHER_USER_ID, TEST_USER_ID


class FakeClient:
    """A `SubstitutionClient` that answers from a script and counts its calls."""

    def __init__(self, result: AiResult | Exception) -> None:
        self.result = result
        self.calls = 0
        self.last_prompt_args: dict[str, object] = {}

    def suggest(self, *, recipe_title: str, missing, pantry) -> AiResult:
        self.calls += 1
        self.last_prompt_args = {
            "recipe_title": recipe_title,
            "missing": list(missing),
            "pantry": list(pantry),
        }
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def ai_settings(**overrides: object) -> Settings:
    """Test settings with AI on. `_env_file=None` so the developer's own .env can't leak in."""
    values: dict[str, object] = {
        "env": "test",
        "ai_enabled": True,
        "anthropic_api_key": "test-key",
        "ai_monthly_budget_cents": 500,
        "ai_daily_substitutions_per_user": 10,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


RESULT = AiResult(
    suggestions=[
        Suggestion(missing_ingredient="Oil", suggestion="Butter", reason="Both carry heat."),
        Suggestion(missing_ingredient="Soy Sauce", suggestion="Salt", reason="Salt alone works."),
    ],
    input_tokens=600,
    output_tokens=450,
)


@pytest.fixture
def fake() -> FakeClient:
    return FakeClient(RESULT)


@pytest.fixture
def ai(client: TestClient, fake: FakeClient) -> Iterator[TestClient]:
    """The API with AI enabled and the model replaced."""
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_substitution_client] = lambda: fake
    yield client
    # The `client` fixture clears every override when it tears down.


@pytest.fixture
def stocked_pantry(session: Session, fixture_recipes: dict[str, int], catalog: dict[str, int]):
    """Three of Egg fried rice's seven ingredients, leaving four missing."""
    for name in ("rice", "egg", "garlic"):
        session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog[name]))
    session.flush()
    return fixture_recipes["Egg fried rice"]


def test_a_first_call_asks_the_model_and_a_second_is_served_from_cache(
    ai: TestClient, fake: FakeClient, stocked_pantry: int
) -> None:
    first = ai.post(f"/recipes/{stocked_pantry}/substitutions")
    assert first.status_code == 200
    assert [s["suggestion"] for s in first.json()["suggestions"]] == ["Butter", "Salt"]
    assert fake.calls == 1

    second = ai.post(f"/recipes/{stocked_pantry}/substitutions")
    assert second.status_code == 200
    assert second.json() == first.json()
    # The whole point: the same question is never paid for twice.
    assert fake.calls == 1


def test_the_prompt_gets_the_missing_ingredients_and_the_whole_pantry(
    ai: TestClient, fake: FakeClient, stocked_pantry: int
) -> None:
    ai.post(f"/recipes/{stocked_pantry}/substitutions")

    assert fake.last_prompt_args["recipe_title"] == "Egg fried rice"
    assert set(fake.last_prompt_args["missing"]) == {"Oil", "Salt", "Soy Sauce", "Spring Onion"}
    assert set(fake.last_prompt_args["pantry"]) == {"Rice", "Egg", "Garlic"}


def test_a_recipe_with_nothing_missing_never_calls_the_model(
    ai: TestClient, fake: FakeClient, session: Session, fixture_recipes: dict[str, int], catalog
) -> None:
    for name in ("flour",):
        session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog[name]))
    session.flush()

    response = ai.post(f"/recipes/{fixture_recipes['Pancakes']}/substitutions")

    assert response.status_code == 200
    assert response.json() == {"suggestions": []}
    assert fake.calls == 0


def test_a_different_pantry_is_a_different_question(
    ai: TestClient, fake: FakeClient, session: Session, stocked_pantry: int, catalog
) -> None:
    """The cache key is the recipe and the pantry, not the user.

    Two cooks with the same pantry are asking the same thing and get the same answer for
    free. Change the pantry and it is a new question, so the model is asked again.
    """
    ai.post(f"/recipes/{stocked_pantry}/substitutions")
    assert fake.calls == 1

    session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog["salt"]))
    session.flush()

    ai.post(f"/recipes/{stocked_pantry}/substitutions")
    assert fake.calls == 2


def test_another_user_with_the_same_pantry_is_served_the_cached_answer(
    ai: TestClient, fake: FakeClient, session: Session, stocked_pantry: int, catalog
) -> None:
    ai.post(f"/recipes/{stocked_pantry}/substitutions")
    assert fake.calls == 1

    session.add(User(id=OTHER_USER_ID))
    session.flush()
    for name in ("rice", "egg", "garlic"):
        session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=catalog[name]))
    session.flush()

    from app.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: OTHER_USER_ID
    response = ai.post(f"/recipes/{stocked_pantry}/substitutions")

    assert response.status_code == 200
    assert fake.calls == 1


def test_the_kill_switch_pauses_the_feature(
    client: TestClient, fake: FakeClient, stocked_pantry: int
) -> None:
    app.dependency_overrides[get_settings] = lambda: ai_settings(
        ai_enabled=False, anthropic_api_key=None
    )
    app.dependency_overrides[get_substitution_client] = lambda: fake

    response = client.post(f"/recipes/{stocked_pantry}/substitutions")

    assert response.status_code == 503
    assert fake.calls == 0


def test_the_monthly_cap_pauses_the_feature(
    ai: TestClient, fake: FakeClient, session: Session, stocked_pantry: int
) -> None:
    session.execute(
        text("INSERT INTO ai_monthly_usage (month, calls, cost_cents) VALUES (:month, 400, 500)"),
        {"month": utc_month()},
    )
    session.flush()

    response = ai.post(f"/recipes/{stocked_pantry}/substitutions")

    assert response.status_code == 503
    assert fake.calls == 0


def test_the_daily_limit_returns_429(
    client: TestClient, fake: FakeClient, session: Session, stocked_pantry: int, catalog
) -> None:
    app.dependency_overrides[get_settings] = lambda: ai_settings(ai_daily_substitutions_per_user=1)
    app.dependency_overrides[get_substitution_client] = lambda: fake

    first = client.post(f"/recipes/{stocked_pantry}/substitutions")
    assert first.status_code == 200

    # A different pantry, so the cache can't answer and the limit has to.
    session.execute(text("DELETE FROM pantry_items WHERE user_id = :u"), {"u": TEST_USER_ID})
    session.flush()
    session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog["salt"]))

    second = client.post(f"/recipes/{stocked_pantry}/substitutions")
    assert second.status_code == 429
    assert fake.calls == 1


def test_a_cached_answer_does_not_use_up_the_daily_allowance(
    client: TestClient, fake: FakeClient, session: Session, stocked_pantry: int
) -> None:
    app.dependency_overrides[get_settings] = lambda: ai_settings(ai_daily_substitutions_per_user=1)
    app.dependency_overrides[get_substitution_client] = lambda: fake

    assert client.post(f"/recipes/{stocked_pantry}/substitutions").status_code == 200
    # Same question. The allowance is used up, but the answer costs nothing to return.
    assert client.post(f"/recipes/{stocked_pantry}/substitutions").status_code == 200
    assert fake.calls == 1


def test_an_unusable_answer_returns_502(
    client: TestClient, session: Session, stocked_pantry: int
) -> None:
    broken = FakeClient(AiUnavailable("stopped with refusal"))
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_substitution_client] = lambda: broken

    response = client.post(f"/recipes/{stocked_pantry}/substitutions")

    assert response.status_code == 502
    assert "usable" in response.json()["detail"]


def test_the_ledger_records_the_tokens_the_response_reported(
    ai: TestClient, session: Session, stocked_pantry: int
) -> None:
    ai.post(f"/recipes/{stocked_pantry}/substitutions")

    month = session.execute(
        text("SELECT calls, input_tokens, output_tokens, cost_cents FROM ai_monthly_usage")
    ).one()
    assert (month.calls, month.input_tokens, month.output_tokens) == (1, 600, 450)
    # 600 * 400 + 450 * 2000 = 1,140,000 millionths of a cent, rounded up.
    assert month.cost_cents == 2

    daily = session.execute(
        text(
            "SELECT calls FROM ai_user_daily_usage WHERE user_id = :u AND day = :d AND feature = :f"
        ),
        {"u": TEST_USER_ID, "d": utc_day(), "f": SUBSTITUTIONS},
    ).scalar()
    assert daily == 1


def test_the_cap_still_fires_when_every_call_costs_less_than_a_cent(
    ai: TestClient, session: Session, stocked_pantry: int
) -> None:
    """The rounding trap, as a test.

    A call of 1,000 input tokens costs 0.4¢. If each call rounded its own cost to an
    integer and added it, every one of these would add zero and the cap could never be
    reached. The ledger accumulates token totals instead and derives the cost from those,
    so 1,250 sub-penny calls really do add up to the 500¢ cap.
    """
    from app.usage import record_call

    settings = ai_settings()
    for _ in range(1250):
        record_call(session, TEST_USER_ID, SUBSTITUTIONS, 1000, 0, settings)

    cost = session.execute(text("SELECT cost_cents FROM ai_monthly_usage")).scalar()
    assert cost == 500

    assert ai.post(f"/recipes/{stocked_pantry}/substitutions").status_code == 503


def test_a_suggestion_already_in_the_pantry_is_marked(
    client: TestClient, session: Session, stocked_pantry: int
) -> None:
    """ "Use the garlic you already have" is worth saying out loud."""
    owned = FakeClient(
        AiResult(
            suggestions=[
                Suggestion(missing_ingredient="Oil", suggestion="Garlic", reason="Pretend."),
                Suggestion(missing_ingredient="Salt", suggestion="Nutmeg", reason="Pretend."),
            ],
            input_tokens=10,
            output_tokens=10,
        )
    )
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_substitution_client] = lambda: owned

    suggestions = client.post(f"/recipes/{stocked_pantry}/substitutions").json()["suggestions"]

    by_name = {s["suggestion"]: s["in_pantry"] for s in suggestions}
    assert by_name == {"Garlic": True, "Nutmeg": False}


def test_a_suggestion_for_something_not_missing_is_dropped(
    client: TestClient, session: Session, stocked_pantry: int
) -> None:
    """What we asked about is ours to decide, not the model's (spec section 4)."""
    confused = FakeClient(
        AiResult(
            suggestions=[
                Suggestion(missing_ingredient="Oil", suggestion="Butter", reason="Fine."),
                Suggestion(missing_ingredient="Rice", suggestion="Quinoa", reason="Not missing."),
                Suggestion(
                    missing_ingredient="Saffron", suggestion="Turmeric", reason="Not asked."
                ),
            ],
            input_tokens=10,
            output_tokens=10,
        )
    )
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_substitution_client] = lambda: confused

    suggestions = client.post(f"/recipes/{stocked_pantry}/substitutions").json()["suggestions"]

    assert [s["missing_ingredient"] for s in suggestions] == ["Oil"]


def test_an_unknown_recipe_returns_404(ai: TestClient, fake: FakeClient) -> None:
    assert ai.post("/recipes/999999/substitutions").status_code == 404
    assert fake.calls == 0


def test_the_ledger_and_the_cache_are_committed(
    ai: TestClient, session: Session, stocked_pantry: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an explicit commit the whole transaction is discarded.

    `get_session` doesn't commit, so a handler that forgets to spends real money and then
    throws away the ledger row and the cache row that justify it. Ordinary tests can't see
    this, because they run inside a transaction they read directly — so this one watches
    for the commit itself.
    """
    commits = 0
    real_commit = session.commit

    def counting_commit() -> None:
        nonlocal commits
        commits += 1
        real_commit()

    monkeypatch.setattr(session, "commit", counting_commit)

    assert ai.post(f"/recipes/{stocked_pantry}/substitutions").status_code == 200
    assert commits == 1


def test_an_unusable_answer_is_still_charged_for(
    client: TestClient, session: Session, stocked_pantry: int
) -> None:
    """A refusal costs money too.

    The tokens were billed whether or not the answer was any good. Recording only the
    answers we liked would leave the monthly cap reading low — and the cap is the one
    guardrail that must never understate spend.
    """
    refused = FakeClient(AiUnavailable("model stopped with refusal", 500, 120))
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_substitution_client] = lambda: refused

    assert client.post(f"/recipes/{stocked_pantry}/substitutions").status_code == 502

    month = session.execute(
        text("SELECT calls, input_tokens, output_tokens, cost_cents FROM ai_monthly_usage")
    ).one()
    assert (month.calls, month.input_tokens, month.output_tokens) == (1, 500, 120)
    # 500 * 400 + 120 * 2000 = 440,000 millionths of a cent, rounded up to 1.
    assert month.cost_cents == 1

    # Nothing was cached: there is no answer worth keeping.
    assert session.execute(text("SELECT count(*) FROM substitution_cache")).scalar() == 0
