"""Unit tests for the liveness endpoint: GET /api/v1/health.

No database dependency — must return quickly regardless of DB state, per
docs/API.md#get-apiv1health.
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


async def test_health_returns_ok(app) -> None:  # type: ignore[no-untyped-def]
    """GET /api/v1/health returns 200 {"status": "ok"} without touching the database."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
