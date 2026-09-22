"""Typed application configuration, read from environment variables (spec section 13).

Locally the values come from `backend/.env`; on Lambda they are set by Terraform.
More settings (DATABASE_URL, AUTH_MODE, Cognito IDs) are added as their milestones arrive.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "test", "prod"] = "local"
    app_version: str = "local"


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process and reuse them (one read per Lambda cold start)."""
    return Settings()
