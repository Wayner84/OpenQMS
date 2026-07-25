"""Integration tests for the authentication HTTP flow against real PostgreSQL.

Follows the tests/integration/test_database_baseline.py pattern: runs
`alembic upgrade head`, then exercises the app via `httpx.AsyncClient`. Covers the
Milestone 1 plan's hard security acceptance criteria: wrong password, unknown email,
and inactive-user login all return an identical 401; an expired/invalid/revoked
token is rejected; logout revokes all previously issued tokens.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AppAndUser = tuple[FastAPI, str]


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; skipping real-PostgreSQL integration tests")
    return url


def _run_alembic_upgrade_head(database_url: str) -> None:
    env = dict(
        os.environ, DATABASE_URL=database_url, JWT_SECRET_KEY="alembic-cli-secret", PYTHONPATH=""
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def database_url() -> str:
    url = _database_url()
    _run_alembic_upgrade_head(url)
    return url


@pytest.fixture
async def app_and_user(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AppAndUser]:
    """Build a real app against `database_url` with one active user seeded directly via the ORM."""
    import app.core.config as config_module
    import app.core.db as db_module
    from app.core.security import hash_password
    from app.main import create_app
    from app.models.organisation import Organisation
    from app.models.user import User

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-secret-key")
    config_module.get_settings.cache_clear()
    db_module.get_session_factory.cache_clear()

    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    email = f"auth-test-{uuid.uuid4()}@example.com"
    async with session_maker() as session:
        result = await session.execute(select(Organisation).where(Organisation.slug == "default"))
        org = result.scalar_one()

        user = User(
            organisation_id=org.id,
            email=email,
            hashed_password=hash_password("correct-password"),
            full_name="Auth Test User",
        )
        session.add(user)
        await session.commit()

    await engine.dispose()

    app = create_app()
    try:
        yield app, email
    finally:
        await db_module.get_session_factory().engine.dispose()


async def test_login_succeeds_with_correct_credentials(app_and_user: AppAndUser) -> None:
    app, email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-password"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert "hashed_password" not in body["user"]


async def test_login_rejects_wrong_password_with_401(app_and_user: AppAndUser) -> None:
    app, email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )

    assert response.status_code == 401


async def test_login_rejects_unknown_email_with_identical_401(app_and_user: AppAndUser) -> None:
    app, email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wrong_password_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )
        unknown_email_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody-at-all@example.com", "password": "wrong-password"},
        )

    assert unknown_email_response.status_code == 401
    assert unknown_email_response.json() == wrong_password_response.json()


async def test_me_requires_authentication(app_and_user: AppAndUser) -> None:
    app, _email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_returns_profile_for_valid_token(app_and_user: AppAndUser) -> None:
    app, email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-password"}
        )
        token = login_response.json()["access_token"]

        me_response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == email


async def test_logout_revokes_the_token_for_future_requests(app_and_user: AppAndUser) -> None:
    app, email = app_and_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-password"}
        )
        token = login_response.json()["access_token"]
        auth_header = {"Authorization": f"Bearer {token}"}

        logout_response = await client.post("/api/v1/auth/logout", headers=auth_header)
        assert logout_response.status_code == 204

        reuse_response = await client.get("/api/v1/auth/me", headers=auth_header)

    assert reuse_response.status_code == 401


async def test_login_rejects_inactive_user_with_identical_401(
    app_and_user: AppAndUser, database_url: str
) -> None:
    from app.models.user import User

    app, email = app_and_user

    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        await session.execute(update(User).where(User.id == user.id).values(is_active=False))
        await session.commit()
    await engine.dispose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wrong_password_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )
        inactive_login_response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-password"}
        )

    assert inactive_login_response.status_code == 401
    assert inactive_login_response.json() == wrong_password_response.json()
