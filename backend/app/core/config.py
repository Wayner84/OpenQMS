"""Typed application settings, loaded from environment variables.

Deployment configuration (database connection, CORS origins, environment name, log
level) is kept separate from database-stored business configuration — see
docs/Architecture.md#configuration-strategy.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Deployment configuration read from environment variables (and `.env` in dev)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    backend_cors_origins: Annotated[list[str], NoDecode] = []
    environment: str = "development"
    log_level: str = "INFO"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow BACKEND_CORS_ORIGINS to be supplied as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance, cached after first construction."""
    return Settings()
