"""Unit tests for the readiness endpoint: GET /api/v1/health/ready.

Exercises DB connectivity against SQLite (ORM-level query only, portable across
engines) per docs/API.md#get-apiv1healthready. Real PostgreSQL behaviour is proven
separately by the integration test.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")

    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.main import create_app

    get_settings.cache_clear()
    get_session_factory.cache_clear()
    return create_app()


async def test_health_ready_returns_ready_when_database_reachable(app: FastAPI) -> None:
    """GET /api/v1/health/ready returns 200 {"status": "ready", "database": "ok"}."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


async def test_health_ready_returns_503_when_database_unreachable(app: FastAPI) -> None:
    """GET /api/v1/health/ready returns 503 when the DB query raises."""
    from app.api.v1 import health as health_module

    class _BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise ConnectionRefusedError("database unreachable")

    async def _broken_session():  # type: ignore[no-untyped-def]
        yield _BrokenSession()

    app.dependency_overrides[health_module.get_session] = _broken_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "error"}
