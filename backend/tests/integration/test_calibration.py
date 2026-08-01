"""Integration tests for the Calibration and Asset Management module against real
PostgreSQL.

Follows the tests/integration/test_products.py pattern. Covers the Milestone 5
plan's hard acceptance criteria for this schema/CRUD slice: organisation isolation
(`404`, never revealing another organisation's ids), `asset_tag` uniqueness (`409`),
`owner_id` cross-organisation validation, and soft delete.

This fixture is self-contained (cleans up every table its own tests create --
`Asset` and `Person` -- in both its setup and its `org_b` teardown) rather than
relying on another integration test file's own setup to clean up after it, per the
cross-file cleanup fragility lesson recorded in
docs/DecisionLog.md#2026-07-30-ncr-attachments-slice-self-contained-integration-test-fixtures-instead-of-relying-on-cross-file-cleanup-ordering.
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
    org_a_headers: dict[str, str]
    org_b_headers: dict[str, str]
    org_a_user_id: uuid.UUID


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
    from app.modules.calibration.models import Asset
    from app.modules.people.models import Person

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

        # Shared, persistent dev database: reset the default organisation's rows so
        # earlier local runs don't affect these assertions. Self-contained (see
        # module docstring) -- Asset must be deleted before Person, since
        # assets.owner_id references people.id.
        await session.execute(delete(Asset).where(Asset.organisation_id == org_a.id))
        await session.execute(delete(Person).where(Person.organisation_id == org_a.id))
        await session.execute(delete(User).where(User.organisation_id == org_a.id))
        await session.commit()

        org_b = Organisation(name=f"Other Org {suffix}", slug=f"other-{suffix}")
        session.add(org_b)
        await session.flush()

        org_a_user = User(
            organisation_id=org_a.id,
            email=f"org-a-user-{suffix}@example.com",
            hashed_password=hash_password("org-a-user-password"),
            full_name="Org A User",
            role=UserRole.ADMIN,
        )
        org_b_user = User(
            organisation_id=org_b.id,
            email=f"org-b-user-{suffix}@example.com",
            hashed_password=hash_password("org-b-user-password"),
            full_name="Org B User",
            role=UserRole.ADMIN,
        )
        session.add_all([org_a_user, org_b_user])
        await session.commit()
        await session.refresh(org_a_user)
        await session.refresh(org_b_user)

    await engine.dispose()

    app = create_app()
    org_a_headers = await _login(app, org_a_user.email, "org-a-user-password")
    org_b_headers = await _login(app, org_b_user.email, "org-b-user-password")

    try:
        yield Context(
            app=app,
            org_a_headers=org_a_headers,
            org_b_headers=org_b_headers,
            org_a_user_id=org_a_user.id,
        )
    finally:
        await db_module.get_session_factory().engine.dispose()

        cleanup_engine = create_async_engine(database_url)
        cleanup_session_maker = async_sessionmaker(cleanup_engine, expire_on_commit=False)
        async with cleanup_session_maker() as cleanup_session:
            await cleanup_session.execute(delete(Asset).where(Asset.organisation_id == org_b.id))
            await cleanup_session.execute(delete(Person).where(Person.organisation_id == org_b.id))
            await cleanup_session.execute(delete(User).where(User.organisation_id == org_b.id))
            await cleanup_session.execute(delete(Organisation).where(Organisation.id == org_b.id))
            await cleanup_session.commit()
        await cleanup_engine.dispose()


async def _create_person(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/people",
        headers=headers,
        json={"first_name": "Olive", "last_name": "Owner", "is_employee": True},
    )
    assert response.status_code == 201, response.text
    person_id: str = response.json()["id"]
    return person_id


async def _create_asset(
    client: AsyncClient, headers: dict[str, str], asset_tag: str = "CAL-001", **overrides: object
) -> str:
    body: dict[str, object] = {
        "asset_tag": asset_tag,
        "name": "Digital caliper",
        "asset_type": "measuring_equipment",
    }
    body.update(overrides)
    response = await client.post("/api/v1/calibration/assets", headers=headers, json=body)
    assert response.status_code == 201, response.text
    asset_id: str = response.json()["id"]
    return asset_id


async def test_create_asset_defaults_to_in_service(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/calibration/assets",
            headers=context.org_a_headers,
            json={
                "asset_tag": "CAL-0001",
                "name": "Digital caliper",
                "asset_type": "measuring_equipment",
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "in_service"
    assert body["created_by_id"] == str(context.org_a_user_id)


async def test_create_asset_rejects_duplicate_asset_tag(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_asset(client, context.org_a_headers, asset_tag="CAL-DUP")
        response = await client.post(
            "/api/v1/calibration/assets",
            headers=context.org_a_headers,
            json={
                "asset_tag": "CAL-DUP",
                "name": "Another caliper",
                "asset_type": "measuring_equipment",
            },
        )

    assert response.status_code == 409


async def test_create_asset_rejects_owner_in_another_organisation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_owner_id = await _create_person(client, context.org_b_headers)
        response = await client.post(
            "/api/v1/calibration/assets",
            headers=context.org_a_headers,
            json={
                "asset_tag": "CAL-0002",
                "name": "Torque wrench",
                "asset_type": "measuring_equipment",
                "owner_id": org_b_owner_id,
            },
        )

    assert response.status_code == 404


async def test_get_asset_returns_404_for_another_organisations_asset(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asset_id = await _create_asset(client, context.org_b_headers)
        response = await client.get(
            f"/api/v1/calibration/assets/{asset_id}", headers=context.org_a_headers
        )

    assert response.status_code == 404


async def test_list_assets_filters_by_status_and_returns_only_the_callers_organisation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_asset(client, context.org_a_headers, asset_tag="CAL-A")
        await _create_asset(
            client, context.org_a_headers, asset_tag="CAL-B", status="out_of_service"
        )
        await _create_asset(client, context.org_b_headers, asset_tag="CAL-A")

        all_response = await client.get("/api/v1/calibration/assets", headers=context.org_a_headers)
        filtered_response = await client.get(
            "/api/v1/calibration/assets",
            headers=context.org_a_headers,
            params={"status": "out_of_service"},
        )

    assert all_response.json()["total"] == 2
    assert filtered_response.json()["total"] == 1
    assert filtered_response.json()["items"][0]["asset_tag"] == "CAL-B"


async def test_update_asset_persists_changes(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asset_id = await _create_asset(client, context.org_a_headers)
        response = await client.patch(
            f"/api/v1/calibration/assets/{asset_id}",
            headers=context.org_a_headers,
            json={
                "asset_tag": "CAL-001",
                "name": "Updated name",
                "asset_type": "measuring_equipment",
                "status": "out_of_service",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated name"
    assert response.json()["status"] == "out_of_service"


async def test_delete_asset_soft_deletes_and_excludes_from_list(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        asset_id = await _create_asset(client, context.org_a_headers)

        delete_response = await client.delete(
            f"/api/v1/calibration/assets/{asset_id}", headers=context.org_a_headers
        )
        get_response = await client.get(
            f"/api/v1/calibration/assets/{asset_id}", headers=context.org_a_headers
        )
        list_response = await client.get(
            "/api/v1/calibration/assets", headers=context.org_a_headers
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert list_response.json()["total"] == 0


async def test_calibration_endpoints_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/calibration/assets")

    assert response.status_code == 401
