"""Integration tests for the Products module against real PostgreSQL.

Follows the tests/integration/test_suppliers.py pattern. Covers the Milestone 3
plan's hard acceptance criteria for this module: organisation isolation (`404`,
never revealing another organisation's ids), `part_number` uniqueness (`409`), the
category "still referenced" delete guard (`409`), and `document_id`/`supplier_id`
cross-organisation validation on the link endpoints.
"""

import asyncio
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
    from app.modules.ncr.models import Ncr
    from app.modules.people.models import Company
    from app.modules.products.models import Product, ProductCategory
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
        # earlier local runs don't affect these assertions. ncrs.product_id/
        # supplier_id reference products.id/suppliers.id, so any leftover NCR row
        # must be cleared first or the deletes below fail on a foreign key
        # violation.
        await session.execute(delete(Ncr).where(Ncr.organisation_id == org_a.id))
        await session.execute(delete(Product).where(Product.organisation_id == org_a.id))
        await session.execute(
            delete(ProductCategory).where(ProductCategory.organisation_id == org_a.id)
        )
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
                delete(Product).where(Product.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(ProductCategory).where(ProductCategory.organisation_id == org_b.id)
            )
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


async def _create_category(
    client: AsyncClient, headers: dict[str, str], name: str = "Fasteners"
) -> str:
    response = await client.post("/api/v1/product-categories", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    category_id: str = response.json()["id"]
    return category_id


async def _create_product(
    client: AsyncClient,
    headers: dict[str, str],
    part_number: str = "PN-001",
    **overrides: object,
) -> str:
    body: dict[str, object] = {
        "part_number": part_number,
        "description": "A widget",
        "type": "internal",
    }
    body.update(overrides)
    response = await client.post("/api/v1/products", headers=headers, json=body)
    assert response.status_code == 201, response.text
    product_id: str = response.json()["id"]
    return product_id


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


# --- Categories --------------------------------------------------------------


async def test_create_and_list_categories(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_category(client, context.org_a_headers, "Fasteners")
        response = await client.get("/api/v1/product-categories", headers=context.org_a_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_get_category_returns_404_for_another_organisations_category(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_id = await _create_category(client, context.org_b_headers, "Org B Category")

        response = await client.get(
            f"/api/v1/product-categories/{category_id}", headers=context.org_a_headers
        )

    assert response.status_code == 404


async def test_delete_category_in_use_returns_409(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_id = await _create_category(client, context.org_a_headers)
        await _create_product(client, context.org_a_headers, category_id=category_id)

        response = await client.delete(
            f"/api/v1/product-categories/{category_id}", headers=context.org_a_headers
        )

    assert response.status_code == 409


async def test_delete_unused_category_succeeds(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_id = await _create_category(client, context.org_a_headers)

        response = await client.delete(
            f"/api/v1/product-categories/{category_id}", headers=context.org_a_headers
        )

    assert response.status_code == 204


# --- Products ------------------------------------------------------------------


async def test_create_product_sets_default_revision_and_creator(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/products",
            headers=context.org_a_headers,
            json={"part_number": "PN-100", "description": "A widget", "type": "purchased"},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revision"] == "A"
    assert body["created_by_id"] == str(context.org_a_user_id)


async def test_create_product_rejects_duplicate_part_number(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_product(client, context.org_a_headers, part_number="PN-DUP")

        response = await client.post(
            "/api/v1/products",
            headers=context.org_a_headers,
            json={"part_number": "PN-DUP", "description": "Another widget", "type": "purchased"},
        )

    assert response.status_code == 409


async def test_create_product_allows_same_part_number_in_different_organisations(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_product(client, context.org_a_headers, part_number="PN-SHARED")

        response = await client.post(
            "/api/v1/products",
            headers=context.org_b_headers,
            json={"part_number": "PN-SHARED", "description": "Also a widget", "type": "purchased"},
        )

    assert response.status_code == 201, response.text


async def test_concurrent_create_with_same_part_number_cannot_both_succeed(
    context: Context,
) -> None:
    """Independent review finding: `_assert_part_number_available` is a check-then-
    insert with no row lock, unlike Document Management's version-number/category-
    tree races (which this milestone's own migration explicitly follows the
    precedent of). Two concurrent creates with the same `part_number` can both pass
    the check before either commits; without catching the resulting `IntegrityError`
    from the `uq_products_org_part_number` constraint, the loser gets a bare 500
    instead of the documented 409. Only real concurrent transactions against a
    database that enforces the unique constraint (Postgres) can exercise this."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = {"part_number": "PN-RACE", "description": "A widget", "type": "purchased"}
        results = await asyncio.gather(
            client.post("/api/v1/products", headers=context.org_a_headers, json=body),
            client.post("/api/v1/products", headers=context.org_a_headers, json=body),
        )

    assert sorted(response.status_code for response in results) == [201, 409]


async def test_get_update_delete_product_returns_404_for_another_organisations_product(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_id = await _create_product(client, context.org_b_headers, part_number="ORG-B-PN")

        get_response = await client.get(
            f"/api/v1/products/{product_id}", headers=context.org_a_headers
        )
        patch_response = await client.patch(
            f"/api/v1/products/{product_id}",
            headers=context.org_a_headers,
            json={"part_number": "ORG-B-PN", "description": "Hijacked", "type": "internal"},
        )
        delete_response = await client.delete(
            f"/api/v1/products/{product_id}", headers=context.org_a_headers
        )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert delete_response.status_code == 404


async def test_list_products_filters_by_category_type_and_search(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_id = await _create_category(client, context.org_a_headers, "Fasteners")
        await _create_product(
            client,
            context.org_a_headers,
            part_number="BOLT-001",
            description="M6 bolt",
            category_id=category_id,
            type="purchased",
        )
        await _create_product(
            client,
            context.org_a_headers,
            part_number="BRACKET-001",
            description="Steel bracket",
            type="internal",
        )

        by_category_response = await client.get(
            f"/api/v1/products?category_id={category_id}", headers=context.org_a_headers
        )
        search_response = await client.get(
            "/api/v1/products?search=bracket", headers=context.org_a_headers
        )

    assert by_category_response.json()["total"] == 1
    assert by_category_response.json()["items"][0]["part_number"] == "BOLT-001"
    assert search_response.json()["total"] == 1
    assert search_response.json()["items"][0]["part_number"] == "BRACKET-001"


# --- Product-document links --------------------------------------------------------


async def test_product_document_link_lifecycle_and_cross_org_document_validation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_id = await _create_product(client, context.org_a_headers)

        org_b_document_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Drawing"}
        )
        org_b_document_id = org_b_document_response.json()["id"]

        cross_org_response = await client.post(
            f"/api/v1/products/{product_id}/documents",
            headers=context.org_a_headers,
            json={"document_id": org_b_document_id, "relationship_type": "drawing"},
        )
        assert cross_org_response.status_code == 404

        document_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "Widget Drawing"}
        )
        document_id = document_response.json()["id"]

        create_response = await client.post(
            f"/api/v1/products/{product_id}/documents",
            headers=context.org_a_headers,
            json={"document_id": document_id, "relationship_type": "drawing"},
        )
        assert create_response.status_code == 201, create_response.text
        link_id = create_response.json()["id"]

        duplicate_response = await client.post(
            f"/api/v1/products/{product_id}/documents",
            headers=context.org_a_headers,
            json={"document_id": document_id, "relationship_type": "drawing"},
        )
        assert duplicate_response.status_code == 409

        second_relationship_response = await client.post(
            f"/api/v1/products/{product_id}/documents",
            headers=context.org_a_headers,
            json={"document_id": document_id, "relationship_type": "specification"},
        )
        assert second_relationship_response.status_code == 201

        list_response = await client.get(
            f"/api/v1/products/{product_id}/documents", headers=context.org_a_headers
        )
        assert list_response.json()["total"] == 2

        delete_response = await client.delete(
            f"/api/v1/products/{product_id}/documents/{link_id}", headers=context.org_a_headers
        )
        assert delete_response.status_code == 204

        final_list_response = await client.get(
            f"/api/v1/products/{product_id}/documents", headers=context.org_a_headers
        )
        assert final_list_response.json()["total"] == 1


async def test_concurrent_duplicate_document_link_cannot_both_succeed(context: Context) -> None:
    """Same TOCTOU class as test_concurrent_create_with_same_part_number_cannot_both_succeed,
    for the duplicate-link check in create_product_document_link."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_id = await _create_product(client, context.org_a_headers)
        document_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "Widget Drawing"}
        )
        document_id = document_response.json()["id"]
        body = {"document_id": document_id, "relationship_type": "drawing"}

        results = await asyncio.gather(
            client.post(
                f"/api/v1/products/{product_id}/documents", headers=context.org_a_headers, json=body
            ),
            client.post(
                f"/api/v1/products/{product_id}/documents", headers=context.org_a_headers, json=body
            ),
        )

    assert sorted(response.status_code for response in results) == [201, 409]


# --- Product-supplier links ---------------------------------------------------------


async def test_product_supplier_link_lifecycle_and_cross_org_supplier_validation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_id = await _create_product(client, context.org_a_headers)

        org_b_company_id = await _create_company(client, context.org_b_headers, "Org B Co")
        org_b_supplier_id = await _create_supplier(client, context.org_b_headers, org_b_company_id)

        cross_org_response = await client.post(
            f"/api/v1/products/{product_id}/suppliers",
            headers=context.org_a_headers,
            json={"supplier_id": org_b_supplier_id},
        )
        assert cross_org_response.status_code == 404

        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)

        create_response = await client.post(
            f"/api/v1/products/{product_id}/suppliers",
            headers=context.org_a_headers,
            json={"supplier_id": supplier_id, "is_preferred": True},
        )
        assert create_response.status_code == 201, create_response.text
        link_id = create_response.json()["id"]
        assert create_response.json()["is_preferred"] is True

        duplicate_response = await client.post(
            f"/api/v1/products/{product_id}/suppliers",
            headers=context.org_a_headers,
            json={"supplier_id": supplier_id},
        )
        assert duplicate_response.status_code == 409

        list_response = await client.get(
            f"/api/v1/products/{product_id}/suppliers", headers=context.org_a_headers
        )
        assert list_response.json()["total"] == 1

        delete_response = await client.delete(
            f"/api/v1/products/{product_id}/suppliers/{link_id}", headers=context.org_a_headers
        )
        assert delete_response.status_code == 204

        final_list_response = await client.get(
            f"/api/v1/products/{product_id}/suppliers", headers=context.org_a_headers
        )
        assert final_list_response.json()["total"] == 0


async def test_concurrent_duplicate_supplier_link_cannot_both_succeed(context: Context) -> None:
    """Same TOCTOU class as test_concurrent_create_with_same_part_number_cannot_both_succeed,
    for the duplicate-link check in create_product_supplier_link."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        product_id = await _create_product(client, context.org_a_headers)
        company_id = await _create_company(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers, company_id)
        body = {"supplier_id": supplier_id}

        results = await asyncio.gather(
            client.post(
                f"/api/v1/products/{product_id}/suppliers", headers=context.org_a_headers, json=body
            ),
            client.post(
                f"/api/v1/products/{product_id}/suppliers", headers=context.org_a_headers, json=body
            ),
        )

    assert sorted(response.status_code for response in results) == [201, 409]


async def test_product_endpoints_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/products")

    assert response.status_code == 401
