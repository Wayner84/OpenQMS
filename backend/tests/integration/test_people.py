"""Integration tests for the People module against real PostgreSQL.

Follows the tests/integration/test_users.py pattern. Covers the Milestone 1 plan's
hard acceptance criteria for this module: organisation isolation (`404`, never
revealing another organisation's ids), the `is_employee`/`company_id` invariant
(`422`), the companies-with-contacts delete guard (`409`), and creator/updater
attribution.
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
    from app.modules.ncr.models import Ncr
    from app.modules.people.models import Company, Person

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
        # earlier local runs don't affect these assertions. ncrs.raised_by_id/
        # owner_id reference people.id, so any leftover NCR row must be cleared
        # first or the Person delete below fails on a foreign key violation.
        await session.execute(delete(Ncr).where(Ncr.organisation_id == org_a.id))
        await session.execute(delete(Person).where(Person.organisation_id == org_a.id))
        await session.execute(delete(Company).where(Company.organisation_id == org_a.id))
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

        # This fixture runs against a shared, persistent dev database, not a
        # per-test-run disposable one, so it must clean up the extra organisation
        # it created -- otherwise test_database_baseline.py's "exactly one
        # organisation" assertion breaks for unrelated test runs.
        cleanup_engine = create_async_engine(database_url)
        cleanup_session_maker = async_sessionmaker(cleanup_engine, expire_on_commit=False)
        async with cleanup_session_maker() as cleanup_session:
            await cleanup_session.execute(delete(Person).where(Person.organisation_id == org_b.id))
            await cleanup_session.execute(
                delete(Company).where(Company.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(User).where(User.organisation_id == org_b.id))
            await cleanup_session.execute(delete(Organisation).where(Organisation.id == org_b.id))
            await cleanup_session.commit()
        await cleanup_engine.dispose()


async def test_create_company_sets_creator_and_defaults_to_other_type(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/companies", headers=context.org_a_headers, json={"name": "Acme Ltd"}
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["type"] == "other"
    assert body["created_by_id"] == str(context.org_a_user_id)
    assert body["updated_by_id"] == str(context.org_a_user_id)


async def test_get_company_returns_404_for_another_organisations_company(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/companies",
            headers=context.org_b_headers,
            json={"name": "Org B Co", "type": "supplier"},
        )
        company_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/companies/{company_id}", headers=context.org_a_headers
        )

    assert response.status_code == 404


async def test_create_person_as_employee_and_as_contact(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_response = await client.post(
            "/api/v1/companies",
            headers=context.org_a_headers,
            json={"name": "Acme Ltd", "type": "customer"},
        )
        company_id = company_response.json()["id"]

        employee_response = await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={"first_name": "Alice", "last_name": "Employee", "is_employee": True},
        )
        contact_response = await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={
                "first_name": "Bob",
                "last_name": "Contact",
                "is_employee": False,
                "company_id": company_id,
            },
        )

    assert employee_response.status_code == 201, employee_response.text
    assert employee_response.json()["company_id"] is None
    assert contact_response.status_code == 201, contact_response.text
    assert contact_response.json()["company_id"] == company_id


async def test_create_person_rejects_employee_company_invariant_violation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={
                "first_name": "Alice",
                "last_name": "Bad",
                "is_employee": True,
                "company_id": str(uuid.uuid4()),
            },
        )

    assert response.status_code == 422


async def test_create_person_rejects_contact_in_another_organisations_company(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_company_response = await client.post(
            "/api/v1/companies",
            headers=context.org_b_headers,
            json={"name": "Org B Co", "type": "supplier"},
        )
        org_b_company_id = org_b_company_response.json()["id"]

        response = await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={
                "first_name": "Eve",
                "last_name": "CrossOrg",
                "is_employee": False,
                "company_id": org_b_company_id,
            },
        )

    assert response.status_code == 404


async def test_get_update_delete_person_returns_404_for_another_organisations_person(
    context: Context,
) -> None:
    """HTTP-level equivalent of the companies cross-org 404 test above, proven through
    the real router/dependency chain for all three by-id person endpoints, not just
    the service-layer unit test."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/people",
            headers=context.org_b_headers,
            json={"first_name": "Org B", "last_name": "Person", "is_employee": True},
        )
        person_id = create_response.json()["id"]

        get_response = await client.get(
            f"/api/v1/people/{person_id}", headers=context.org_a_headers
        )
        patch_response = await client.patch(
            f"/api/v1/people/{person_id}",
            headers=context.org_a_headers,
            json={"first_name": "Hijacked", "last_name": "Person", "is_employee": True},
        )
        delete_response = await client.delete(
            f"/api/v1/people/{person_id}", headers=context.org_a_headers
        )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


async def test_company_with_contacts_endpoint_lists_only_that_companys_people(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_response = await client.post(
            "/api/v1/companies",
            headers=context.org_a_headers,
            json={"name": "Acme Ltd", "type": "customer"},
        )
        company_id = company_response.json()["id"]

        await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={
                "first_name": "Bob",
                "last_name": "Contact",
                "is_employee": False,
                "company_id": company_id,
            },
        )
        await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={"first_name": "Alice", "last_name": "Employee", "is_employee": True},
        )

        response = await client.get(
            f"/api/v1/companies/{company_id}/people", headers=context.org_a_headers
        )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["first_name"] == "Bob"


async def test_delete_company_with_contacts_returns_409(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_response = await client.post(
            "/api/v1/companies",
            headers=context.org_a_headers,
            json={"name": "Acme Ltd", "type": "customer"},
        )
        company_id = company_response.json()["id"]

        await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={
                "first_name": "Bob",
                "last_name": "Contact",
                "is_employee": False,
                "company_id": company_id,
            },
        )

        response = await client.delete(
            f"/api/v1/companies/{company_id}", headers=context.org_a_headers
        )

    assert response.status_code == 409


async def test_delete_company_without_contacts_succeeds(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_response = await client.post(
            "/api/v1/companies", headers=context.org_a_headers, json={"name": "Acme Ltd"}
        )
        company_id = company_response.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/companies/{company_id}", headers=context.org_a_headers
        )
        get_response = await client.get(
            f"/api/v1/companies/{company_id}", headers=context.org_a_headers
        )

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


async def test_people_search_filters_by_name(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={"first_name": "Zelda", "last_name": "Zephyr", "is_employee": True},
        )
        await client.post(
            "/api/v1/people",
            headers=context.org_a_headers,
            json={"first_name": "Alice", "last_name": "Anderson", "is_employee": True},
        )

        response = await client.get(
            "/api/v1/people", headers=context.org_a_headers, params={"search": "zephyr"}
        )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["first_name"] == "Zelda"


async def test_people_and_companies_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        companies_response = await client.get("/api/v1/companies")
        people_response = await client.get("/api/v1/people")

    assert companies_response.status_code == 401
    assert people_response.status_code == 401
