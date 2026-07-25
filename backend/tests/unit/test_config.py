"""Unit tests for the typed application Settings object."""

import pytest


def test_settings_reads_required_fields_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings must load DATABASE_URL, CORS origins, environment, and log level from env vars."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://openqms:changeme@localhost:5432/openqms")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

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

    from app.core.config import Settings

    with pytest.raises(Exception):
        Settings(_env_file=None)  # type: ignore[call-arg]
