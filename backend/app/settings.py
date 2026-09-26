"""Typed application configuration, read from environment variables (spec section 13).

Locally the values come from `backend/.env`; on Lambda they are set by Terraform.
Cognito settings arrive with the login milestone (M5).
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "test", "prod"] = "local"
    app_version: str = "local"

    # SQLAlchemy URL, e.g. postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy
    # In production the value comes from SSM instead; see spec 10.7.
    database_url: str = "postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy"

    # "shared" treats every caller as one fixed user; "cognito" verifies a real token (M5).
    auth_mode: Literal["shared", "cognito"] = "shared"
    # Deliberate escape hatch for the live site between M4 and M5. Removed when login ships.
    allow_shared_mode: bool = False

    @model_validator(mode="after")
    def refuse_shared_mode_in_production(self) -> Self:
        """Production must never serve an unauthenticated API by accident (spec 10.4)."""
        if self.env == "prod" and self.auth_mode == "shared" and not self.allow_shared_mode:
            raise ValueError(
                "AUTH_MODE=shared is not allowed when ENV=prod; "
                "set ALLOW_SHARED_MODE=true to override before login ships."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process and reuse them (one read per Lambda cold start)."""
    return Settings()
