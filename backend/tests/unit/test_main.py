"""Unit tests for the FastAPI app factory: CORS allow-list configuration."""

from starlette.middleware.cors import CORSMiddleware


def test_create_app_configures_cors_allow_list(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """create_app() must attach CORSMiddleware restricted to the configured origin allow-list."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    app = create_app()

    cors_middlewares = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors_middlewares) == 1
    assert cors_middlewares[0].kwargs["allow_origins"] == ["http://localhost:5173"]
