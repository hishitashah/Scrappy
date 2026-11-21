"""Scrappy's MCP server: the pantry, recipe matching and grocery list as tools for an AI
assistant.

The Model Context Protocol (MCP) is how an assistant such as Claude Code or Claude Desktop
reaches an outside system. With this server connected, a cook can say "I just bought
spinach and feta, what can I make?" and the assistant adds both to the pantry, ranks
recipes, and puts what's still missing on the grocery list, using the same tables the web
app reads.

See `server.py` for the tools and `__main__.py` for how it starts. Not part of the API: it
lives outside `app/` so the Lambda package never carries it, and its one dependency (`mcp`)
is in the dev group, which the Lambda build leaves out.
"""
