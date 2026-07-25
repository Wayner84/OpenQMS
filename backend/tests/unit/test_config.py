"""Unit tests for the typed application Settings object."""

import pytest
from pydantic import ValidationError


def test_settings_reads_required_fields_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must load DATABASE_URL, CORS origins, environment, and log level from env vars."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://openqms:changeme@localhost:5432/openqms"
    )
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")

    from app.core.config import Settings

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://openqms:changeme@localhost:5432/openqms"
    assert settings.backend_cors_origins == [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    assert settings.environment == "development"
    assert settings.log_level == "INFO"


def test_settings_rejects_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """DATABASE_URL is mandatory; Settings must fail fast rather than silently default."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_missing_jwt_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT_SECRET_KEY is mandatory with no default; the app must not start without one."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://openqms:changeme@localhost:5432/openqms"
    )
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_defaults_jwt_expiry_and_bootstrap_admin_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JWT expiry defaults to 60 minutes; bootstrap admin vars default to unset."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://openqms:changeme@localhost:5432/openqms"
    )
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
    monkeypatch.delenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    from app.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.jwt_access_token_expire_minutes == 60
    assert settings.bootstrap_admin_email is None
    assert settings.bootstrap_admin_password is None
