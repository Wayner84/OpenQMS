"""Integration tests for organisation-scoped user management against real PostgreSQL.

Follows the tests/integration/test_auth.py pattern. Covers the Milestone 1 plan's
hard acceptance criteria for this module: admin-only enforcement (`403` for a
member), cross-organisation isolation (`404`, never revealing another
organisation's user ids), duplicate-email `409`, and the self-deactivation /
last-admin guards (`409`).
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


@dataclass
class Context:
    app: FastAPI
    org_a_admin_headers: dict[str, str]
    org_a_member_headers: dict[str, str]
    org_b_admin_headers: dict[str, str]
    org_a_admin_id: uuid.UUID
    org_a_member_id: uuid.UUID
    org_b_admin_id: uuid.UUID
    org_a_member_email: str
    org_a_member_password: str


async def _login(app: FastAPI, email: str, password: str) -> dict[str, str]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def context(database_url: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Context]:
    import app.core.config as config_module
    import app.core.db as db_module
    from app.core.security import hash_password
    from app.main import create_app
    from app.models.organisation import Organisation
    from app.models.user import User, UserRole

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-secret-key")
    config_module.get_settings.cache_clear()
    db_module.get_session_factory.cache_clear()

    suffix = uuid.uuid4().hex[:8]
    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        org_a = (
            await session.execute(select(Organisation).where(Organisation.slug == "default"))
        ).scalar_one()

        # This fixture runs against a shared, persistent dev database, not a fresh
        # one per test run. Reset the default organisation's users first so
        # pagination/listing assertions below aren't affected by rows left behind by
        # earlier local test runs (a real CI run against a disposable database
        # would not need this).
        await session.execute(delete(User).where(User.organisation_id == org_a.id))
        await session.commit()

        org_b = Organisation(name=f"Other Org {suffix}", slug=f"other-{suffix}")
        session.add(org_b)
        await session.flush()

        org_a_admin = User(
            organisation_id=org_a.id,
            email=f"org-a-admin-{suffix}@example.com",
            hashed_password=hash_password("org-a-admin-password"),
            full_name="Org A Admin",
            role=UserRole.ADMIN,
        )
        org_a_member = User(
            organisation_id=org_a.id,
            email=f"org-a-member-{suffix}@example.com",
            hashed_password=hash_password("org-a-member-password"),
            full_name="Org A Member",
            role=UserRole.MEMBER,
        )
        org_b_admin = User(
            organisation_id=org_b.id,
            email=f"org-b-admin-{suffix}@example.com",
            hashed_password=hash_password("org-b-admin-password"),
            full_name="Org B Admin",
            role=UserRole.ADMIN,
        )
        session.add_all([org_a_admin, org_a_member, org_b_admin])
        await session.commit()
        await session.refresh(org_a_admin)
        await session.refresh(org_a_member)
        await session.refresh(org_b_admin)

    await engine.dispose()

    app = create_app()
    org_a_admin_headers = await _login(app, org_a_admin.email, "org-a-admin-password")
    org_a_member_headers = await _login(app, org_a_member.email, "org-a-member-password")
    org_b_admin_headers = await _login(app, org_b_admin.email, "org-b-admin-password")

    try:
        yield Context(
            app=app,
            org_a_admin_headers=org_a_admin_headers,
            org_a_member_headers=org_a_member_headers,
            org_b_admin_headers=org_b_admin_headers,
            org_a_admin_id=org_a_admin.id,
            org_a_member_id=org_a_member.id,
            org_b_admin_id=org_b_admin.id,
            org_a_member_email=org_a_member.email,
            org_a_member_password="org-a-member-password",
        )
    finally:
        await db_module.get_session_factory().engine.dispose()

        # This fixture runs against a shared, persistent dev database (not a
        # per-test-run disposable one), so it must clean up the extra organisation
        # it created -- otherwise test_database_baseline.py's "exactly one
        # organisation" assertion breaks for unrelated test runs.
        cleanup_engine = create_async_engine(database_url)
        cleanup_session_maker = async_sessionmaker(cleanup_engine, expire_on_commit=False)
        async with cleanup_session_maker() as cleanup_session:
            await cleanup_session.execute(delete(User).where(User.organisation_id == org_b.id))
            await cleanup_session.execute(delete(Organisation).where(Organisation.id == org_b.id))
            await cleanup_session.commit()
        await cleanup_engine.dispose()


async def test_admin_can_create_a_user_in_their_own_organisation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/users",
            headers=context.org_a_admin_headers,
            json={
                "email": f"new-{uuid.uuid4().hex[:8]}@example.com",
                "full_name": "New User",
                "password": "a-strong-password",
                "role": "member",
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "member"
    assert "hashed_password" not in body


async def test_member_cannot_create_users(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/users",
            headers=context.org_a_member_headers,
            json={
                "email": "blocked@example.com",
                "full_name": "Blocked",
                "password": "a-strong-password",
                "role": "member",
            },
        )

    assert response.status_code == 403


async def test_member_cannot_list_users(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/users", headers=context.org_a_member_headers)

    assert response.status_code == 403


async def test_list_users_only_returns_the_admins_own_organisation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/users", headers=context.org_a_admin_headers)

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(context.org_a_admin_id) in ids
    assert str(context.org_a_member_id) in ids
    assert str(context.org_b_admin_id) not in ids


async def test_create_user_rejects_duplicate_email_with_409(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        me_response = await client.get("/api/v1/auth/me", headers=context.org_a_admin_headers)
        existing_email = me_response.json()["email"]

        response = await client.post(
            "/api/v1/users",
            headers=context.org_a_admin_headers,
            json={
                "email": existing_email,
                "full_name": "Duplicate",
                "password": "a-strong-password",
                "role": "member",
            },
        )

    assert response.status_code == 409


async def test_update_user_returns_404_for_another_organisations_user(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/users/{context.org_b_admin_id}",
            headers=context.org_a_admin_headers,
            json={"is_active": False},
        )

    assert response.status_code == 404


async def test_admin_cannot_deactivate_themselves(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/users/{context.org_a_admin_id}",
            headers=context.org_a_admin_headers,
            json={"is_active": False},
        )

    assert response.status_code == 409


async def test_admin_can_deactivate_a_member(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/users/{context.org_a_member_id}",
            headers=context.org_a_admin_headers,
            json={"is_active": False},
        )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_a_second_admin_can_demote_the_first_once_two_admins_exist(context: Context) -> None:
    """Promoting a member to admin, then having *that new admin* demote the original
    admin, must succeed: two active admins existed at the time of the demotion (a
    distinct caller from the target), so the guard (which only blocks dropping to
    zero active admins) must not fire.
    """
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        promote_response = await client.patch(
            f"/api/v1/users/{context.org_a_member_id}",
            headers=context.org_a_admin_headers,
            json={"role": "admin"},
        )
        assert promote_response.status_code == 200

        new_admin_headers = await _login(
            context.app, context.org_a_member_email, context.org_a_member_password
        )
        demote_original_response = await client.patch(
            f"/api/v1/users/{context.org_a_admin_id}",
            headers=new_admin_headers,
            json={"role": "member"},
        )

    assert demote_original_response.status_code == 200
    assert demote_original_response.json()["role"] == "member"


async def test_reactivating_a_deactivated_user_is_allowed(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        deactivate_response = await client.patch(
            f"/api/v1/users/{context.org_a_member_id}",
            headers=context.org_a_admin_headers,
            json={"is_active": False},
        )
        assert deactivate_response.status_code == 200

        reactivate_response = await client.patch(
            f"/api/v1/users/{context.org_a_member_id}",
            headers=context.org_a_admin_headers,
            json={"is_active": True},
        )

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True
