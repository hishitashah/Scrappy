"""Start the server over stdio: `uv run python -m mcp_server`, from `backend/`.

It is a local, single-user developer tool. The assistant on this machine launches it as a
subprocess and talks to it over stdin and stdout, so there is no network listener and no
token to check: it reaches the database in DATABASE_URL directly, as one user, and
whoever can start it already holds that URL.

- SCRAPPY_MCP_USER_ID picks the user. It defaults to "shared-user", the user the local web
  app runs as in shared auth mode, so the assistant and the browser see the same pantry.
- With ENV=prod it refuses to start, as the API refuses shared auth there (spec 10.4).

Nothing may print to stdout: that stream carries the protocol itself.
"""

import os

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import SHARED_USER_ID
from app.db import get_engine
from app.models import User
from app.settings import get_settings
from mcp_server.server import build_server


def main() -> None:
    if get_settings().env == "prod":
        raise SystemExit("The Scrappy MCP server is a local tool and does not run with ENV=prod.")

    user_id = os.environ.get("SCRAPPY_MCP_USER_ID", SHARED_USER_ID)
    engine = get_engine()
    # Pantry and grocery rows reference users.id, so the user must exist before any write,
    # exactly as `get_current_user` makes sure of on every API request.
    with Session(engine) as session:
        session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
        session.commit()

    build_server(lambda: Session(engine), user_id).run()


if __name__ == "__main__":
    main()
