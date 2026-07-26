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

    # Authentication (Milestone 1) — see docs/DecisionLog.md for the JWT/Argon2id
    # decision and .hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md.
    jwt_secret_key: str
    jwt_access_token_expire_minutes: int = 60
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None

    # File storage (Milestone 2) -- the `openqms_uploads` Docker volume, reserved
    # since Milestone 0, is mounted here. See
    # docs/Database.md#documents-and-related-tables-milestone-2.
    uploads_dir: str = "/app/uploads"
    # Defense-in-depth request-body size cap, checked before any request body is
    # read -- see docs/DecisionLog.md#2026-07-26-document-upload-request-body-size-cap.
    # Deliberately larger than the default per-organisation document_upload_policy
    # max_size_mb (50 MB) to leave headroom for multipart overhead and non-file
    # form fields without needing to move in lockstep with that configurable value.
    max_request_body_mb: int = 200

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
