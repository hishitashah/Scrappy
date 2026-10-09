"""Typed application configuration, read from environment variables (spec section 13).

Locally the values come from `backend/.env`; on Lambda they are set by Terraform.
Cognito settings arrive with the login milestone (M5).
"""

import os
from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Region every Scrappy resource lives in (spec section 2).
AWS_REGION = "us-east-1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "test", "prod"] = "local"
    app_version: str = "local"

    # SQLAlchemy URL, e.g. postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy
    database_url: str = "postgresql+psycopg://scrappy:scrappy@localhost:5433/scrappy"
    # Production sets this instead, and the URL is read from SSM (spec 10.7). The secret
    # therefore never appears in Terraform state, a Lambda environment variable, or git.
    database_url_param: str | None = None

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


def _read_ssm_parameter(name: str) -> str:
    """Fetch and decrypt one SecureString.

    boto3 is imported here rather than at module level because the Lambda runtime provides
    it and the deployment package deliberately leaves it out (spec 10.8). Locally and in
    tests this function is never reached, since DATABASE_URL is set.
    """
    import boto3

    client = boto3.client("ssm", region_name=AWS_REGION)
    response = client.get_parameter(Name=name, WithDecryption=True)
    return str(response["Parameter"]["Value"])


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process and reuse them (one read per Lambda cold start).

    This is also the only SSM call: the cache means a warm Lambda never fetches again.
    """
    settings = Settings()
    if settings.database_url_param and "DATABASE_URL" not in os.environ:
        settings.database_url = _read_ssm_parameter(settings.database_url_param)
    return settings
