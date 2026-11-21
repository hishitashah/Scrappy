"""The MCP server (`mcp_server/`), every tool called through a real MCP client.

The client connects in-process, so each call goes through the protocol itself (the tool
listing, JSON-RPC, argument validation against each tool's input schema) and lands in the
test's own session, whose writes are rolled back like every other test's.
"""

from contextlib import nullcontext
from typing import Any

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from sqlalchemy import select
from sqlalchemy.orm import Session

import mcp_server.__main__ as entrypoint
from app.models import GroceryItem, PantryItem, Recipe, RecipeIngredient, User
from app.settings import Settings
from mcp_server.server import build_server
from tests.conftest import OTHER_USER_ID

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def server(session: Session, test_user: str) -> MCPServer:
    # nullcontext: the tools must not close the test's session, which the fixture rolls back.
    return build_server(lambda: nullcontext(session), test_user)


async def call(server: MCPServer, tool: str, **arguments: Any) -> Any:
    """Call a tool that should succeed and return its structured result."""
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    content = result.structured_content
    assert content is not None
    # A tool that returns a list has it wrapped as {"result": [...]} on the wire.
    return content.get("result", content)


async def call_error(server: MCPServer, tool: str, **arguments: Any) -> str:
    """Call a tool that should fail and return the message the model would read."""
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert result.is_error
    return result.content[0].text


def names(items: list[dict[str, Any]]) -> list[str]:
    return [item["name"] for item in items]


def pantry_ids(session: Session, user_id: str) -> set[int]:
    return set(
        session.scalars(select(PantryItem.ingredient_id).where(PantryItem.user_id == user_id))
    )


async def test_lists_every_tool_with_read_only_hints(server: MCPServer) -> None:
    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == {
        "get_pantry",
        "add_to_pantry",
        "remove_from_pantry",
        "find_recipes",
        "get_recipe",
        "add_missing_to_grocery_list",
        "get_grocery_list",
        "search_ingredients",
    }
    # Clients use the hint to decide which calls need the user's approval.
    read_only = {name for name, tool in tools.items() if tool.annotations.read_only_hint}
    assert read_only == {
        "get_pantry",
        "find_recipes",
        "get_recipe",
        "get_grocery_list",
        "search_ingredients",
    }


async def test_add_to_pantry_resolves_names_through_the_catalog(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    # "Eggs" reaches "egg" through normalization and its alias, as typing it in the app does.
    result = await call(server, "add_to_pantry", ingredients=["Eggs", "rice", "unicorn"])

    assert result["added"] == ["Egg", "Rice"]
    assert result["not_found"] == ["unicorn"]
    assert names(result["pantry"]) == ["Egg", "Rice"]
    assert pantry_ids(session, "test-user") == {catalog["egg"], catalog["rice"]}


async def test_add_to_pantry_with_only_unknown_names_changes_nothing(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    result = await call(server, "add_to_pantry", ingredients=["unicorn"])

    assert result == {"pantry": [], "added": [], "not_found": ["unicorn"]}
    assert pantry_ids(session, "test-user") == set()


async def test_add_to_pantry_rejects_an_empty_list(server: MCPServer) -> None:
    message = await call_error(server, "add_to_pantry", ingredients=[])

    assert "at least 1 item" in message


async def test_buying_an_ingredient_takes_it_off_the_grocery_list(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    session.add(GroceryItem(user_id="test-user", ingredient_id=catalog["egg"]))
    session.flush()

    await call(server, "add_to_pantry", ingredients=["egg"])

    assert await call(server, "get_grocery_list") == []


async def test_remove_from_pantry(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    await call(server, "add_to_pantry", ingredients=["egg", "rice"])

    pantry = await call(server, "remove_from_pantry", ingredient="Eggs")

    assert names(pantry) == ["Rice"]
    assert names(await call(server, "get_pantry")) == ["Rice"]


async def test_removing_something_not_in_the_pantry_is_an_error(
    server: MCPServer, catalog: dict[str, int]
) -> None:
    message = await call_error(server, "remove_from_pantry", ingredient="garlic")

    assert "'garlic' is not in the pantry" in message


async def test_find_recipes_ranks_with_the_matching_query(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    await call(server, "add_to_pantry", ingredients=["egg"])

    results = await call(server, "find_recipes")

    # Egg plus the assumed water and salt make all of "Boiled egg" (spec 10.2's example).
    assert results[0] == {
        "recipe_id": fixture_recipes["Boiled egg"],
        "title": "Boiled egg",
        "match_percent": 100,
        "have": 3,
        "total": 3,
        "missing": [],
        "ai_written": False,
    }
    # Under the 50% floor, so it isn't offered at all.
    assert "Egg fried rice" not in [result["title"] for result in results]


async def test_find_recipes_with_an_empty_pantry_finds_nothing(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    assert await call(server, "find_recipes") == []


async def test_get_recipe_marks_what_the_cook_has(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    await call(server, "add_to_pantry", ingredients=["egg"])

    recipe = await call(server, "get_recipe", recipe_id=fixture_recipes["Egg fried rice"])

    have = {line["name"]: line["have"] for line in recipe["ingredients"]}
    assert have["Egg"] is True
    assert have["Salt"] is True  # an assumed staple
    assert have["Rice"] is False
    assert recipe["missing"] == [name for name, owned in have.items() if not owned]
    assert recipe["steps"] == ["Cook."]


async def test_get_recipe_for_an_unknown_id_is_an_error(server: MCPServer) -> None:
    message = await call_error(server, "get_recipe", recipe_id=999_999)

    assert "No recipe with id 999999" in message


async def test_another_cooks_generated_recipe_does_not_exist(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    session.add(User(id=OTHER_USER_ID))
    session.flush()
    recipe = Recipe(
        source="generated",
        title="Their secret omelette",
        steps=["Whisk."],
        created_by=OTHER_USER_ID,
    )
    session.add(recipe)
    session.flush()
    session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=catalog["egg"], position=0))
    session.flush()

    message = await call_error(server, "get_recipe", recipe_id=recipe.id)
    assert f"No recipe with id {recipe.id}" in message

    await call(server, "add_to_pantry", ingredients=["egg"])
    titles = [result["title"] for result in await call(server, "find_recipes")]
    assert "Their secret omelette" not in titles


async def test_add_missing_to_grocery_list(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    await call(server, "add_to_pantry", ingredients=["egg"])
    recipe = await call(server, "get_recipe", recipe_id=fixture_recipes["Egg fried rice"])

    result = await call(
        server, "add_missing_to_grocery_list", recipe_id=fixture_recipes["Egg fried rice"]
    )

    assert result["added"] == recipe["missing"]
    assert "Egg" not in names(result["grocery_list"])
    assert sorted(names(result["grocery_list"])) == sorted(recipe["missing"])
    assert names(await call(server, "get_grocery_list")) == names(result["grocery_list"])


async def test_add_missing_for_a_recipe_with_nothing_missing_adds_nothing(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    await call(server, "add_to_pantry", ingredients=["egg"])

    result = await call(
        server, "add_missing_to_grocery_list", recipe_id=fixture_recipes["Boiled egg"]
    )

    assert result == {"grocery_list": [], "added": []}


async def test_search_ingredients_ranks_the_most_used_first(
    server: MCPServer, fixture_recipes: dict[str, int]
) -> None:
    # Case-insensitive, and ranked by how many recipes use each match (egg is in two).
    results = await call(server, "search_ingredients", query="EG")

    assert [result["name"] for result in results] == ["Egg"]
    assert results[0]["recipe_count"] == 2


async def test_search_ingredients_needs_a_real_name(server: MCPServer) -> None:
    # Punctuation normalizes to nothing, and an empty search would match every ingredient.
    message = await call_error(server, "search_ingredients", query="%")

    assert "'%' isn't an ingredient name" in message


async def test_tools_never_touch_another_cooks_rows(
    server: MCPServer, session: Session, catalog: dict[str, int]
) -> None:
    session.add(User(id=OTHER_USER_ID))
    session.flush()
    session.add(PantryItem(user_id=OTHER_USER_ID, ingredient_id=catalog["garlic"]))
    session.add(GroceryItem(user_id=OTHER_USER_ID, ingredient_id=catalog["rice"]))
    session.flush()

    assert await call(server, "get_pantry") == []
    assert await call(server, "get_grocery_list") == []
    await call(server, "add_to_pantry", ingredients=["rice"])

    assert pantry_ids(session, OTHER_USER_ID) == {catalog["garlic"]}
    other_list = session.scalars(
        select(GroceryItem.ingredient_id).where(GroceryItem.user_id == OTHER_USER_ID)
    ).all()
    assert other_list == [catalog["rice"]]


def test_refuses_to_start_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    production = Settings(
        env="prod", auth_mode="cognito", cognito_user_pool_id="pool", cognito_client_id="client"
    )
    monkeypatch.setattr(entrypoint, "get_settings", lambda: production)

    with pytest.raises(SystemExit, match="does not run with ENV=prod"):
        entrypoint.main()
