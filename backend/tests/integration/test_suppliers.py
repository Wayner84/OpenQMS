"""Integration tests for the Suppliers module against real PostgreSQL.

Follows the tests/integration/test_people.py pattern. Covers the Milestone 3 plan's
hard acceptance criteria for this module: organisation isolation (`404`, never
revealing another organisation's ids), `company_id`/`certificate_document_id`
cross-organisation validation, and the certification-expiry window endpoint.
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
    from app.models.configuration import Configuration
    from app.models.organisation import Organisation
    from app.models.user import User, UserRole
    from app.modules.documents.models import Document
    from app.modules.people.models import Company
    from app.modules.suppliers.models import Supplier

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
        # earlier local runs don't affect these assertions.
        await session.execute(delete(Supplier).where(Supplier.organisation_id == org_a.id))
        await session.execute(delete(Document).where(Document.organisation_id == org_a.id))
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

        cleanup_engine = create_async_engine(database_url)
        cleanup_session_maker = async_sessionmaker(cleanup_engine, expire_on_commit=False)
        async with cleanup_session_maker() as cleanup_session:
            await cleanup_session.execute(
                delete(Supplier).where(Supplier.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(Document).where(Document.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(Company).where(Company.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(User).where(User.organisation_id == org_b.id))
            await cleanup_session.execute(
                delete(Configuration).where(Configuration.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(Organisation).where(Organisation.id == org_b.id))
            await cleanup_session.commit()
        await cleanup_engine.dispose()


async def _create_company(
    client: AsyncClient, headers: dict[str, str], name: str = "Acme Ltd"
) -> str:
    response = await client.post(
        "/api/v1/companies", headers=headers, json={"name": name, "type": "supplier"}
    )
    assert response.status_code == 201, response.text
    company_id: str = response.json()["id"]
    return company_id


async def _create_supplier(client: AsyncClient, headers: dict[str, str], company_id: str) -> str:
    response = await client.post(
        "/api/v1/suppliers", headers=headers, json={"company_id": company_id}
    )
    assert response.status_code == 201, response.text
    supplier_id: str = response.json()["id"]
    return supplier_id


async def test_create_supplier_sets_creator_and_defaults(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = await _create_company(client, context.org_a_headers)
        response = await client.post(
            "/api/v1/suppliers", headers=context.org_a_headers, json={"company_id": company_id}
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["approval_status"] == "pending"
    assert body["is_preferred"] is False
    assert body["created_by_id"] == str(context.org_a_user_id)


async def test_create_supplier_rejects_company_in_another_organisation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_company_id = await _create_company(client, context.org_b_headers, "Org B Co")

        response = await client.post(
            "/api/v1/suppliers",
            headers=context.org_a_headers,
            json={"company_id": org_b_company_id},
        )

    assert response.status_code == 404


async def test_get_update_delete_supplier_returns_404_for_another_organisations_supplier(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_company_id = await _create_company(client, context.org_b_headers, "Org B Co")
        supplier_id = await _create_supplier(client, context.org_b_headers, org_b_company_id)

        get_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}", headers=context.org_a_headers
        )
        patch_response = await client.patch(
            f"/api/v1/suppliers/{supplier_id}",
            headers=context.org_a_headers,
            json={"company_id": org_b_company_id, "approval_status": "approved"},
        )
        delete_response = await client.delete(
            f"/api/v1/suppliers/{supplier_id}", headers=context.org_a_headers
        )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


async def test_list_suppliers_filters_by_approval_status_and_search(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        acme_id = await _create_company(client, context.org_a_headers, "Acme Ltd")
        globex_id = await _create_company(client, context.org_a_headers, "Globex Corp")

        acme_supplier = await _create_supplier(client, context.org_a_headers, acme_id)
        await client.patch(
            f"/api/v1/suppliers/{acme_supplier}",
            headers=context.org_a_headers,
            json={"company_id": acme_id, "approval_status": "approved"},
        )
        await _create_supplier(client, context.org_a_headers, globex_id)

        approved_response = await client.get(
            "/api/v1/suppliers?approval_status=approved", headers=context.org_a_headers
        )
        search_response = await client.get(
            "/api/v1/suppliers?search=globex", headers=context.org_a_headers
        )

    assert approved_response.status_code == 200
    approved_body = approved_response.json()
    assert approved_body["total"] == 1
    assert approved_body["items"][0]["id"] == acme_supplier

    assert search_response.status_code == 200
    search_body = search_response.json()
    assert search_body["total"] == 1
    assert search_body["items"][0]["company_id"] == globex_id


async def test_certification_crud_and_cross_org_document_validation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)

        org_b_document_response = await client.post(
            "/api/v1/documents",
            headers=context.org_b_headers,
            json={"title": "Org B Certificate"},
        )
        org_b_document_id = org_b_document_response.json()["id"]

        cross_org_response = await client.post(
            f"/api/v1/suppliers/{supplier_id}/certifications",
            headers=context.org_a_headers,
            json={"certification_type": "ISO 9001", "certificate_document_id": org_b_document_id},
        )
        assert cross_org_response.status_code == 404

        create_response = await client.post(
            f"/api/v1/suppliers/{supplier_id}/certifications",
            headers=context.org_a_headers,
            json={
                "certification_type": "ISO 9001",
                "issued_date": "2026-01-01",
                "expiry_date": "2027-01-01",
            },
        )
        assert create_response.status_code == 201, create_response.text
        certification_id = create_response.json()["id"]

        update_response = await client.patch(
            f"/api/v1/suppliers/{supplier_id}/certifications/{certification_id}",
            headers=context.org_a_headers,
            json={"certification_type": "AS9100", "expiry_date": "2027-06-01"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["certification_type"] == "AS9100"

        list_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/certifications", headers=context.org_a_headers
        )
        assert list_response.json()["total"] == 1

        cross_org_get_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/certifications", headers=context.org_b_headers
        )
        assert cross_org_get_response.status_code == 404

        delete_response = await client.delete(
            f"/api/v1/suppliers/{supplier_id}/certifications/{certification_id}",
            headers=context.org_a_headers,
        )
        assert delete_response.status_code == 204

        final_list_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/certifications", headers=context.org_a_headers
        )
        assert final_list_response.json()["total"] == 0


async def test_expiring_certifications_endpoint_respects_within_days_and_organisation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)

        await client.post(
            f"/api/v1/suppliers/{supplier_id}/certifications",
            headers=context.org_a_headers,
            json={"certification_type": "Expiring soon", "expiry_date": "2026-08-05"},
        )
        await client.post(
            f"/api/v1/suppliers/{supplier_id}/certifications",
            headers=context.org_a_headers,
            json={"certification_type": "Far future", "expiry_date": "2030-01-01"},
        )

        org_b_company_id = await _create_company(client, context.org_b_headers, "Org B Co")
        org_b_supplier_id = await _create_supplier(client, context.org_b_headers, org_b_company_id)
        await client.post(
            f"/api/v1/suppliers/{org_b_supplier_id}/certifications",
            headers=context.org_b_headers,
            json={"certification_type": "Org B expiring", "expiry_date": "2026-08-05"},
        )

        response = await client.get(
            "/api/v1/suppliers/certifications/expiring?within_days=3650",
            headers=context.org_a_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    types = {item["certification_type"] for item in body["items"]}
    assert types == {"Expiring soon", "Far future"}


async def test_performance_record_create_and_list_is_append_only(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)

        create_response = await client.post(
            f"/api/v1/suppliers/{supplier_id}/performance",
            headers=context.org_a_headers,
            json={"period": "2026-Q1", "score": "88.50"},
        )
        assert create_response.status_code == 201, create_response.text
        assert create_response.json()["created_by_id"] == str(context.org_a_user_id)

        list_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/performance", headers=context.org_a_headers
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        cross_org_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/performance", headers=context.org_b_headers
        )
        assert cross_org_response.status_code == 404


async def test_performance_records_list_newest_first(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)

        await client.post(
            f"/api/v1/suppliers/{supplier_id}/performance",
            headers=context.org_a_headers,
            json={"period": "2026-Q1", "score": "80.00"},
        )
        await client.post(
            f"/api/v1/suppliers/{supplier_id}/performance",
            headers=context.org_a_headers,
            json={"period": "2026-Q2", "score": "90.00"},
        )

        list_response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/performance", headers=context.org_a_headers
        )

    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [item["period"] for item in items] == ["2026-Q2", "2026-Q1"]


async def test_supplier_endpoints_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/suppliers")

    assert response.status_code == 401
