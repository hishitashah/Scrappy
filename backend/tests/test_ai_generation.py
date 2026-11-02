"""POST /recipes/generate (spec 10.12).

The Anthropic client is replaced throughout, so these tests never reach the network and
never spend money. What they verify is everything around the call: that the model's names
land on the catalog instead of duplicating it, that the recipe belongs to one user and is
invisible to everyone else, and that the ledger ends up holding the real token counts.

There is deliberately no cache here, unlike F7: pressing the button again means "give me a
different recipe", so each press is a new question and a new row.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import (
    AiUnavailable,
    GeneratedLine,
    GeneratedRecipe,
    GenerationResult,
    get_generation_client,
)
from app.auth import get_current_user
from app.main import app
from app.models import Ingredient, PantryItem, User
from app.settings import get_settings
from app.usage import GENERATION, utc_day, utc_month
from tests.conftest import OTHER_USER_ID, TEST_USER_ID
from tests.test_ai_substitutions import ai_settings


class FakeGenerationClient:
    """A `GenerationClient` that answers from a script and counts its calls."""

    def __init__(self, result: GenerationResult | Exception) -> None:
        self.result = result
        self.calls = 0
        self.last_pantry: list[str] = []

    def generate(self, *, pantry) -> GenerationResult:
        self.calls += 1
        self.last_pantry = list(pantry)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def result(*lines: tuple[str, str | None], title: str = "Garlic Fried Rice") -> GenerationResult:
    return GenerationResult(
        recipe=GeneratedRecipe(
            title=title,
            lines=[GeneratedLine(display_name=name, measure=measure) for name, measure in lines],
            steps=["Boil the rice.", "Fry it with the egg and garlic."],
        ),
        input_tokens=700,
        output_tokens=900,
    )


# "Eggs" is deliberately plural: it normalizes to `egg`, which the fixture catalog already
# holds, so the common case is a name that has to find an existing row.
RESULT = result(("Rice", "2 cups"), ("Eggs", "2"), ("Garlic", "3 cloves"))


@pytest.fixture
def fake() -> FakeGenerationClient:
    return FakeGenerationClient(RESULT)


@pytest.fixture
def ai(client: TestClient, fake: FakeGenerationClient) -> Iterator[TestClient]:
    """The API with AI enabled and the model replaced."""
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: fake
    yield client
    # The `client` fixture clears every override when it tears down.


@pytest.fixture
def pantry(session: Session, catalog: dict[str, int]) -> dict[str, int]:
    """Three real ingredients, which is enough to ask for a recipe."""
    for name in ("rice", "egg", "garlic"):
        session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog[name]))
    session.flush()
    return catalog


def test_a_generated_recipe_is_saved_to_the_caller(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    response = ai.post("/recipes/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Garlic Fried Rice"
    assert body["generated"] is True
    assert body["steps"] == ["Boil the rice.", "Fry it with the egg and garlic."]
    # A generated recipe has no category, cuisine, photo, video or source, and invents none.
    assert (body["category"], body["area"], body["image_url"]) == (None, None, None)
    assert (body["youtube_url"], body["source_url"]) == (None, None)

    row = session.execute(
        text("SELECT source, source_id, created_by FROM recipes WHERE id = :id"),
        {"id": body["id"]},
    ).one()
    assert (row.source, row.source_id, row.created_by) == ("generated", None, TEST_USER_ID)


def test_the_prompt_gets_the_whole_pantry(
    ai: TestClient, fake: FakeGenerationClient, pantry: dict[str, int]
) -> None:
    ai.post("/recipes/generate")

    assert set(fake.last_pantry) == {"Rice", "Egg", "Garlic"}


def test_returned_names_reuse_catalog_rows_rather_than_duplicating_them(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """ "Eggs" has to find the `egg` row the pantry already points at.

    If it didn't, the recipe would list an ingredient the cook owns as missing, and the
    catalog would grow a near-duplicate for every plural the model happened to use.
    """
    body = ai.post("/recipes/generate").json()

    ids = [ingredient["id"] for ingredient in body["ingredients"]]
    assert set(ids) == {pantry["rice"], pantry["egg"], pantry["garlic"]}
    assert session.scalar(text("SELECT count(*) FROM ingredients WHERE name = 'egg'")) == 1
    # Read back under the catalog's own label, not the model's wording.
    assert [ingredient["display_name"] for ingredient in body["ingredients"]] == [
        "Rice",
        "Egg",
        "Garlic",
    ]


def test_an_unknown_ingredient_joins_the_catalog(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """A name that maps to nothing is created, exactly as the import does (spec 10.12)."""
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        result(("Rice", "2 cups"), ("Fish Sauce", "1 tbsp"))
    )

    body = client.post("/recipes/generate").json()

    created = session.scalar(text("SELECT display_name FROM ingredients WHERE name = 'fish sauce'"))
    assert created == "Fish Sauce"
    assert "Fish Sauce" in [ingredient["display_name"] for ingredient in body["ingredients"]]


def test_an_empty_pantry_is_refused_without_calling_the_model(
    ai: TestClient, fake: FakeGenerationClient
) -> None:
    """Nothing to cook from, so nothing to ask — and no allowance spent finding out."""
    response = ai.post("/recipes/generate")

    assert response.status_code == 422
    assert fake.calls == 0


def test_a_pantry_of_nothing_but_water_is_still_empty(
    ai: TestClient, session: Session, fake: FakeGenerationClient, catalog: dict[str, int]
) -> None:
    """Water is assumed everywhere, but it is not a reason to think there is food."""
    session.execute(text("DELETE FROM pantry_items WHERE user_id = :u"), {"u": TEST_USER_ID})
    session.add(PantryItem(user_id=TEST_USER_ID, ingredient_id=catalog["water"]))
    session.flush()

    assert ai.post("/recipes/generate").status_code == 200
    assert fake.calls == 1


def test_an_off_pantry_ingredient_is_kept_and_reported_as_missing(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """The prompt asks for the pantry and nothing else; models add salt anyway.

    Keeping the line is the honest answer: the recipe reports what it really needs, and
    the method still makes sense. Dropping it would promise a recipe the cook can make
    while leaving "season with salt" in step 2 referring to nothing.
    """
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        result(("Rice", "2 cups"), ("Salt", "1 tsp"))
    )

    body = client.post("/recipes/generate").json()

    owned = {ingredient["display_name"]: ingredient["owned"] for ingredient in body["ingredients"]}
    assert owned == {"Rice": True, "Salt": False}


def test_two_lines_that_mean_one_ingredient_collapse(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """(recipe_id, ingredient_id) is the primary key, so a repeat would be a crash."""
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        result(("Eggs", "2"), ("Egg", "1 more"))
    )

    body = client.post("/recipes/generate").json()

    assert [ingredient["display_name"] for ingredient in body["ingredients"]] == ["Egg"]


def test_a_nameless_line_is_skipped_rather_than_stored(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """Punctuation normalizes to nothing, and nothing is not an ingredient.

    Without a guard this inserts a row with an empty `name` that every user's autocomplete
    then carries, because the catalog is shared.
    """
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        result(("Rice", "2 cups"), ("—", "a pinch"))
    )

    body = client.post("/recipes/generate").json()

    assert [ingredient["display_name"] for ingredient in body["ingredients"]] == ["Rice"]
    assert session.scalar(text("SELECT count(*) FROM ingredients WHERE name = ''")) == 0


def test_the_recipe_appears_in_its_owners_matches_labeled(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    generated = ai.post("/recipes/generate").json()

    matches = ai.get("/matches").json()

    mine = [match for match in matches if match["id"] == generated["id"]]
    assert len(mine) == 1
    assert mine[0]["generated"] is True
    # Built from the pantry, so it is a complete match and sorts to the top.
    assert mine[0]["match"] == 100
    assert matches[0]["id"] == generated["id"]


def test_an_imported_recipe_is_not_labeled_generated(
    ai: TestClient, session: Session, fixture_recipes: dict[str, int], pantry: dict[str, int]
) -> None:
    matches = ai.get("/matches").json()

    assert matches, "the fixture pantry should match the fixture recipes"
    assert all(match["generated"] is False for match in matches)


def test_a_generated_recipe_is_invisible_to_everyone_else(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    generated = ai.post("/recipes/generate").json()

    session.add(User(id=OTHER_USER_ID))
    session.flush()
    for name in ("rice", "egg", "garlic"):
        session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=pantry[name]))
    session.flush()
    app.dependency_overrides[get_current_user] = lambda: OTHER_USER_ID

    # Not in their results, and not readable by id either.
    assert all(match["id"] != generated["id"] for match in ai.get("/matches").json())
    assert ai.get(f"/recipes/{generated['id']}").status_code == 404


def test_the_detail_endpoint_reports_a_generated_recipe(
    ai: TestClient, pantry: dict[str, int]
) -> None:
    """Where the badge comes from on a revisit.

    The browser navigates to /recipes/{id} after generating, so if this endpoint didn't
    report `generated` the label would vanish the moment the page was reloaded.
    """
    generated = ai.post("/recipes/generate").json()

    reread = ai.get(f"/recipes/{generated['id']}").json()

    assert reread["generated"] is True
    assert reread == generated


def test_each_press_writes_a_new_recipe(
    ai: TestClient, fake: FakeGenerationClient, session: Session, pantry: dict[str, int]
) -> None:
    """No cache, by design: pressing again means "give me a different idea"."""
    first = ai.post("/recipes/generate").json()
    second = ai.post("/recipes/generate").json()

    assert first["id"] != second["id"]
    assert fake.calls == 2
    assert session.scalar(text("SELECT count(*) FROM recipes WHERE source = 'generated'")) == 2


def test_the_kill_switch_pauses_the_feature(
    client: TestClient, fake: FakeGenerationClient, pantry: dict[str, int]
) -> None:
    app.dependency_overrides[get_settings] = lambda: ai_settings(
        ai_enabled=False, anthropic_api_key=None
    )
    app.dependency_overrides[get_generation_client] = lambda: fake

    assert client.post("/recipes/generate").status_code == 503
    assert fake.calls == 0


def test_the_monthly_cap_pauses_the_feature(
    ai: TestClient, fake: FakeGenerationClient, session: Session, pantry: dict[str, int]
) -> None:
    session.execute(
        text("INSERT INTO ai_monthly_usage (month, calls, cost_cents) VALUES (:month, 400, 500)"),
        {"month": utc_month()},
    )
    session.flush()

    assert ai.post("/recipes/generate").status_code == 503
    assert fake.calls == 0


def test_the_daily_limit_returns_429(
    client: TestClient, fake: FakeGenerationClient, session: Session, pantry: dict[str, int]
) -> None:
    """Three a day, and nothing to fall back on: generation has no cache."""
    app.dependency_overrides[get_settings] = lambda: ai_settings(ai_daily_generations_per_user=2)
    app.dependency_overrides[get_generation_client] = lambda: fake

    assert client.post("/recipes/generate").status_code == 200
    assert client.post("/recipes/generate").status_code == 200

    third = client.post("/recipes/generate")
    assert third.status_code == 429
    assert "limit" in third.json()["detail"]
    assert fake.calls == 2


def test_the_substitution_allowance_is_counted_separately(
    client: TestClient, fake: FakeGenerationClient, session: Session, pantry: dict[str, int]
) -> None:
    """One feature using up its day must not close the other one down."""
    from app.usage import SUBSTITUTIONS, record_call

    settings = ai_settings(ai_daily_generations_per_user=1)
    for _ in range(50):
        record_call(session, TEST_USER_ID, SUBSTITUTIONS, 10, 10, settings)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_generation_client] = lambda: fake

    assert client.post("/recipes/generate").status_code == 200


def test_an_unreachable_model_returns_502_and_records_no_spend(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        AiUnavailable("anthropic call failed: AuthenticationError")
    )

    response = client.post("/recipes/generate")

    assert response.status_code == 502
    assert session.scalar(text("SELECT count(*) FROM ai_monthly_usage")) == 0
    # Nothing half-written: a recipe is saved only once there is a recipe to save.
    assert session.scalar(text("SELECT count(*) FROM recipes WHERE source = 'generated'")) == 0


def test_an_unusable_answer_is_still_charged_for(
    client: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """A refusal or a truncated recipe costs money too.

    Truncation is the likely one here: 8192 tokens is generous for a recipe, but thinking
    comes out of the same ceiling. Recording only the answers we liked would leave the
    monthly cap reading low, and the cap must never understate spend.
    """
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        AiUnavailable("model stopped with max_tokens", 500, 120)
    )

    assert client.post("/recipes/generate").status_code == 502

    month = session.execute(
        text("SELECT calls, input_tokens, output_tokens, cost_cents FROM ai_monthly_usage")
    ).one()
    assert (month.calls, month.input_tokens, month.output_tokens) == (1, 500, 120)
    # 500 * 400 + 120 * 2000 = 440,000 millionths of a cent, rounded up to 1.
    assert month.cost_cents == 1
    assert session.scalar(text("SELECT count(*) FROM recipes WHERE source = 'generated'")) == 0


def test_the_ledger_records_the_tokens_the_response_reported(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    ai.post("/recipes/generate")

    month = session.execute(
        text("SELECT calls, input_tokens, output_tokens, cost_cents FROM ai_monthly_usage")
    ).one()
    assert (month.calls, month.input_tokens, month.output_tokens) == (1, 700, 900)
    # 700 * 400 + 900 * 2000 = 2,080,000 millionths of a cent, rounded up to 3.
    assert month.cost_cents == 3

    daily = session.scalar(
        text(
            "SELECT calls FROM ai_user_daily_usage WHERE user_id = :u AND day = :d AND feature = :f"
        ),
        {"u": TEST_USER_ID, "d": utc_day(), "f": GENERATION},
    )
    assert daily == 1


def test_the_ledger_and_the_recipe_are_committed(
    ai: TestClient, session: Session, pantry: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an explicit commit the whole transaction is discarded.

    `get_session` doesn't commit, so a handler that forgets spends real money and then
    throws away both the ledger row and the recipe that justify it. Ordinary tests can't
    see this, because they run inside a transaction they read directly — so this one
    watches for the commit itself.
    """
    commits = 0
    real_commit = session.commit

    def counting_commit() -> None:
        nonlocal commits
        commits += 1
        real_commit()

    monkeypatch.setattr(session, "commit", counting_commit)

    assert ai.post("/recipes/generate").status_code == 200
    assert commits == 1


def test_an_invented_ingredient_sorts_last_in_autocomplete(
    client: TestClient, session: Session, fixture_recipes: dict[str, int], pantry: dict[str, int]
) -> None:
    """The accepted cost of creating catalog rows from a model's output (spec 10.12).

    A name the model invented joins the catalog everyone's autocomplete reads. That is
    survivable because suggestions are ranked by how many recipes use an ingredient, so a
    brand-new one arrives with a count of 1 and sits behind everything real.
    """
    app.dependency_overrides[get_settings] = lambda: ai_settings()
    app.dependency_overrides[get_generation_client] = lambda: FakeGenerationClient(
        result(("Rice", "2 cups"), ("Galangal Paste", "1 tsp"))
    )
    client.post("/recipes/generate")

    catalog = client.get("/ingredients").json()

    invented = next(item for item in catalog if item["display_name"] == "Galangal Paste")
    assert invented["recipe_count"] == 1
    assert max(item["recipe_count"] for item in catalog) > 1


def test_a_generated_ingredient_can_be_added_to_a_pantry(
    ai: TestClient, session: Session, pantry: dict[str, int]
) -> None:
    """A created row is a real ingredient, not a second-class one."""
    body = ai.post("/recipes/generate").json()
    ingredient_id = body["ingredients"][0]["id"]

    session.execute(text("DELETE FROM pantry_items WHERE user_id = :u"), {"u": TEST_USER_ID})
    session.flush()
    response = ai.post("/pantry/items", json={"ingredient_ids": [ingredient_id]})

    assert response.status_code == 200
    assert session.get(Ingredient, ingredient_id) is not None
