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

    # "shared" treats every caller as one fixed user; "cognito" verifies a real token.
    auth_mode: Literal["shared", "cognito"] = "shared"
    # Deliberate escape hatch for the live site between M4 and M5. Removed when login ships.
    allow_shared_mode: bool = False

    # Set by Terraform from the Cognito outputs; required once AUTH_MODE=cognito.
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None

    # --- AI features (F7, F8). Backend only: no AI setting is ever exposed to the browser.
    #
    # The key comes from the environment locally and from SSM on Lambda, like the database
    # URL. Tests set neither, because they replace the client rather than call it.
    anthropic_api_key: str | None = None
    anthropic_api_key_param: str | None = None

    # The kill switch (spec 14, guardrail 5): flipping this to false disables both AI
    # features without a deploy. Off by default, so nothing can spend by accident.
    ai_enabled: bool = False
    ai_model: str = "claude-opus-5-5"

    # The hard cap. $5 a month, checked before every call that would spend.
    ai_monthly_budget_cents: int = 500
    ai_daily_substitutions_per_user: int = 10
    ai_daily_generations_per_user: int = 3

    # Claude Opus 5.5 list price, in cents per million tokens ($4 in, $20 out). Config
    # rather than code, so a price change is a deploy variable and not a patch.
    ai_input_cents_per_mtok: int = 400
    ai_output_cents_per_mtok: int = 2000

    @property
    def cognito_issuer(self) -> str:
        """The `iss` claim every token from this pool carries."""
        return f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{self.cognito_user_pool_id}"

    @property
    def cognito_jwks_url(self) -> str:
        """Where Cognito publishes the public keys that verify its signatures."""
        return f"{self.cognito_issuer}/.well-known/jwks.json"

    @model_validator(mode="after")
    def refuse_shared_mode_in_production(self) -> Self:
        """Production must never serve an unauthenticated API by accident (spec 10.4)."""
        if self.env == "prod" and self.auth_mode == "shared" and not self.allow_shared_mode:
            raise ValueError(
                "AUTH_MODE=shared is not allowed when ENV=prod; "
                "set ALLOW_SHARED_MODE=true to override before login ships."
            )
        return self

    @model_validator(mode="after")
    def require_an_api_key_when_ai_is_enabled(self) -> Self:
        """Catch "enabled but no key" at startup, not on the first button press."""
        if self.ai_enabled and not (self.anthropic_api_key or self.anthropic_api_key_param):
            raise ValueError(
                "AI_ENABLED=true requires ANTHROPIC_API_KEY or ANTHROPIC_API_KEY_PARAM"
            )
        return self

    @model_validator(mode="after")
    def require_cognito_settings(self) -> Self:
        """Catch a half-configured pool at startup, not on the first request."""
        if self.auth_mode == "cognito" and not (
            self.cognito_user_pool_id and self.cognito_client_id
        ):
            raise ValueError(
                "AUTH_MODE=cognito requires COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID"
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
    # Only when AI is actually on: while the kill switch is off the parameter still exists
    # but holds a placeholder, and there is no reason to spend a cold start fetching it.
    if (
        settings.ai_enabled
        and settings.anthropic_api_key_param
        and "ANTHROPIC_API_KEY" not in os.environ
    ):
        settings.anthropic_api_key = _read_ssm_parameter(settings.anthropic_api_key_param)
    return settings
