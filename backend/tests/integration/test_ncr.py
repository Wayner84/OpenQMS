"""Integration tests for the NCR module against real PostgreSQL.

Follows the tests/integration/test_products.py pattern. Covers the Milestone 4
plan's hard acceptance criteria for this schema/CRUD/workflow slice: organisation
isolation (`404`, never revealing another organisation's ids), the type/supplier_id
invariant (`422`), cross-module `product_id`/`supplier_id`/`raised_by_id`
validation, the one-directional transition workflow (`409` for an invalid
transition), admin-only deletion, and a real-concurrency race on the transition
lock (kept as documentation of intended behaviour -- see
docs/DecisionLog.md#2026-07-29-milestone-3-closeout-products-check-then-insert-races-mapped-to-clean-conflicts
for the same scheduler-dependency caveat already recorded for this style of test).
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
    from app.modules.ncr.numbering import DEFAULT_NUMBERING_SCHEME, NUMBERING_SCHEME_KEY
    from app.modules.people.models import Company, Person
    from app.modules.products.models import Product
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
        # earlier local runs don't affect these assertions. This file's own tests
        # create Person/Company/Product/Supplier/Document rows via helper functions
        # (not just Ncr rows), so -- unlike relying on the next alphabetically-run
        # file's own setup to clean up after this one -- this fixture cleans up all
        # of them itself, keeping this file self-contained regardless of which
        # other integration test files run before or after it in a given session.
        # ncr_attachments.document_id has no ON DELETE, so Ncr (which cascades to
        # ncr_attachments) must be deleted before Document.
        await session.execute(delete(Ncr).where(Ncr.organisation_id == org_a.id))
        await session.execute(delete(Document).where(Document.organisation_id == org_a.id))
        await session.execute(delete(Product).where(Product.organisation_id == org_a.id))
        await session.execute(delete(Supplier).where(Supplier.organisation_id == org_a.id))
        await session.execute(delete(Person).where(Person.organisation_id == org_a.id))
        await session.execute(delete(Company).where(Company.organisation_id == org_a.id))
        await session.execute(delete(User).where(User.organisation_id == org_a.id))
        # Also reset the NCR numbering scheme to its default sequence state -- a
        # shared, persistent dev database, not a per-test-run disposable one, so an
        # earlier run's incremented next_sequence would otherwise leak into this
        # run's exact-number assertions (matching test_documents.py's equivalent
        # reset for document_numbering_scheme).
        await session.execute(
            delete(Configuration).where(
                Configuration.organisation_id == org_a.id, Configuration.key == NUMBERING_SCHEME_KEY
            )
        )
        session.add(
            Configuration(
                organisation_id=org_a.id,
                key=NUMBERING_SCHEME_KEY,
                value={key: dict(value) for key, value in DEFAULT_NUMBERING_SCHEME.items()},
            )
        )
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
            # ncr_attachments.document_id has no ON DELETE, so Ncr (which cascades to
            # ncr_attachments) must be deleted before Document -- matching the setup
            # cleanup above. Some of this file's tests create an org_b Document to
            # validate cross-organisation attachment rejection, so it must be cleaned
            # up here too or it blocks the org_b User delete below.
            await cleanup_session.execute(delete(Ncr).where(Ncr.organisation_id == org_b.id))
            await cleanup_session.execute(
                delete(Document).where(Document.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(Product).where(Product.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(Supplier).where(Supplier.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(Person).where(Person.organisation_id == org_b.id))
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


async def _create_person(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/people",
        headers=headers,
        json={"first_name": "Quinn", "last_name": "Reporter", "is_employee": True},
    )
    assert response.status_code == 201, response.text
    person_id: str = response.json()["id"]
    return person_id


async def _create_product(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={"part_number": "PN-001", "description": "A widget", "type": "internal"},
    )
    assert response.status_code == 201, response.text
    product_id: str = response.json()["id"]
    return product_id


async def _create_document(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/documents", headers=headers, json={"title": "Inspection photo"}
    )
    assert response.status_code == 201, response.text
    document_id: str = response.json()["id"]
    return document_id


async def _create_supplier(client: AsyncClient, headers: dict[str, str]) -> str:
    company_response = await client.post(
        "/api/v1/companies", headers=headers, json={"name": "Acme Ltd", "type": "supplier"}
    )
    assert company_response.status_code == 201, company_response.text
    company_id = company_response.json()["id"]
    supplier_response = await client.post(
        "/api/v1/suppliers", headers=headers, json={"company_id": company_id}
    )
    assert supplier_response.status_code == 201, supplier_response.text
    supplier_id: str = supplier_response.json()["id"]
    return supplier_id


async def _create_ncr(
    client: AsyncClient, headers: dict[str, str], raised_by_id: str, **overrides: object
) -> str:
    body: dict[str, object] = {
        "type": "internal",
        "raised_by_id": raised_by_id,
        "description": "A widget was out of spec",
    }
    body.update(overrides)
    response = await client.post("/api/v1/ncr", headers=headers, json=body)
    assert response.status_code == 201, response.text
    ncr_id: str = response.json()["id"]
    return ncr_id


# --- Create ----------------------------------------------------------------------


async def test_create_ncr_generates_a_number_and_defaults_to_open(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)

        response = await client.post(
            "/api/v1/ncr",
            headers=context.org_a_headers,
            json={"type": "internal", "raised_by_id": raised_by_id, "description": "Issue"},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["number"] == "NCR-0001"
    assert body["status"] == "open"
    assert body["created_by_id"] == str(context.org_a_user_id)


async def test_create_ncr_rejects_supplier_type_without_supplier_id(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)

        response = await client.post(
            "/api/v1/ncr",
            headers=context.org_a_headers,
            json={"type": "supplier", "raised_by_id": raised_by_id, "description": "Issue"},
        )

    assert response.status_code == 422


async def test_create_ncr_rejects_internal_type_with_supplier_id(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers)

        response = await client.post(
            "/api/v1/ncr",
            headers=context.org_a_headers,
            json={
                "type": "internal",
                "supplier_id": supplier_id,
                "raised_by_id": raised_by_id,
                "description": "Issue",
            },
        )

    assert response.status_code == 422


async def test_create_ncr_rejects_product_in_another_organisation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        org_b_product_id = await _create_product(client, context.org_b_headers)

        response = await client.post(
            "/api/v1/ncr",
            headers=context.org_a_headers,
            json={
                "type": "internal",
                "product_id": org_b_product_id,
                "raised_by_id": raised_by_id,
                "description": "Issue",
            },
        )

    assert response.status_code == 404


# --- Get / list / update / delete -------------------------------------------------


async def test_get_ncr_returns_404_for_another_organisations_ncr(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.get(f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers)

    assert response.status_code == 404


async def test_list_ncrs_filters_by_status_and_returns_only_the_callers_organisation(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        await _create_ncr(client, context.org_a_headers, raised_by_id)
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.get(
            "/api/v1/ncr", headers=context.org_a_headers, params={"status": "open"}
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_update_ncr_persists_changes(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        response = await client.patch(
            f"/api/v1/ncr/{ncr_id}",
            headers=context.org_a_headers,
            json={
                "type": "internal",
                "raised_by_id": raised_by_id,
                "description": "Updated description",
                "root_cause_summary": "Tooling wear",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["description"] == "Updated description"
    assert response.json()["root_cause_summary"] == "Tooling wear"


async def test_delete_ncr_requires_admin(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-ncr-delete@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(
            context.app, "member-ncr-delete@example.com", "member-password"
        )

        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        member_response = await client.delete(f"/api/v1/ncr/{ncr_id}", headers=member_headers)
        assert member_response.status_code == 403

        admin_response = await client.delete(f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers)
        assert admin_response.status_code == 204

        get_response = await client.get(f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers)
        assert get_response.status_code == 404


async def test_concurrent_delete_and_transition_cannot_both_succeed(context: Context) -> None:
    """Independent review finding: a transition racing an admin delete could land
    on (and add status-history rows to) an NCR that is now soft-deleted, since
    _lock_ncr didn't re-check deleted_at post-lock. Fixed by locking in delete_ncr
    too and re-checking deleted_at after the lock in transition_ncr. Real
    concurrent requests against Postgres can exercise this -- kept as
    documentation of intended behaviour, not a guaranteed deterministic
    reproduction (same caveat as test_concurrent_transitions_cannot_both_succeed
    above)."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        results = await asyncio.gather(
            client.delete(f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers),
            client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": "investigate"},
            ),
        )

        delete_response, transition_response = results
        assert delete_response.status_code == 204
        # Whichever operation reached the lock first determines the outcome; either
        # order is a valid, non-corrupting resolution -- the guarantee under test
        # is that the transition can never silently succeed against an
        # already-deleted NCR while also leaving it looking undeleted.
        assert transition_response.status_code in (200, 404)
        if transition_response.status_code == 200:
            get_response = await client.get(f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers)
            assert get_response.status_code == 404


# --- Transition workflow -----------------------------------------------------------


async def test_transition_walks_the_full_sequence_and_records_history(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        for to_status in [
            "investigate",
            "containment",
            "corrective_action",
            "verification",
            "closed",
        ]:
            response = await client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": to_status, "comments": f"Moving to {to_status}"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == to_status

        assert response.json()["closed_at"] is not None

        history_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/status-history", headers=context.org_a_headers
        )
        assert history_response.status_code == 200
        assert history_response.json()["total"] == 6


async def test_transition_rejects_skipping_a_stage_with_409(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        response = await client.post(
            f"/api/v1/ncr/{ncr_id}/transition",
            headers=context.org_a_headers,
            json={"to_status": "containment"},
        )

    assert response.status_code == 409


async def test_transition_returns_404_for_another_organisations_ncr(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.post(
            f"/api/v1/ncr/{ncr_id}/transition",
            headers=context.org_a_headers,
            json={"to_status": "investigate"},
        )

    assert response.status_code == 404


async def test_concurrent_transitions_cannot_both_succeed(context: Context) -> None:
    """Real concurrent transactions against a database that actually enforces row
    locks (Postgres) can exercise the `_lock_ncr` guard -- kept as documentation of
    intended behaviour, not a guaranteed deterministic reproduction (same caveat as
    test_concurrent_reciprocal_reparenting_cannot_both_succeed in test_documents.py)."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        results = await asyncio.gather(
            client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": "investigate"},
            ),
            client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": "investigate"},
            ),
        )

    assert sorted(response.status_code for response in results) == [200, 409]


async def test_ncr_endpoints_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ncr")

    assert response.status_code == 401


# --- Actions -----------------------------------------------------------------


async def test_action_lifecycle_and_cross_org_owner_validation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        org_b_person_id = await _create_person(client, context.org_b_headers)
        cross_org_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/actions",
            headers=context.org_a_headers,
            json={"description": "Should fail", "owner_id": org_b_person_id},
        )
        assert cross_org_response.status_code == 404

        create_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/actions",
            headers=context.org_a_headers,
            json={"description": "Retrain operator", "owner_id": raised_by_id},
        )
        assert create_response.status_code == 201, create_response.text
        action_id = create_response.json()["id"]
        assert create_response.json()["status"] == "open"

        list_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/actions", headers=context.org_a_headers
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        complete_response = await client.patch(
            f"/api/v1/ncr/actions/{action_id}",
            headers=context.org_a_headers,
            json={
                "description": "Retrain operator",
                "owner_id": raised_by_id,
                "status": "complete",
            },
        )
        assert complete_response.status_code == 200, complete_response.text
        assert complete_response.json()["status"] == "complete"
        assert complete_response.json()["completed_at"] is not None


async def test_create_action_returns_404_for_another_organisations_ncr(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.post(
            f"/api/v1/ncr/{ncr_id}/actions",
            headers=context.org_a_headers,
            json={"description": "Should not be created"},
        )

    assert response.status_code == 404


async def test_update_action_returns_404_for_another_organisations_action(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        org_b_ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)
        action_response = await client.post(
            f"/api/v1/ncr/{org_b_ncr_id}/actions",
            headers=context.org_b_headers,
            json={"description": "Org B action"},
        )
        assert action_response.status_code == 201, action_response.text
        action_id = action_response.json()["id"]

        response = await client.patch(
            f"/api/v1/ncr/actions/{action_id}",
            headers=context.org_a_headers,
            json={"description": "Hijacked", "status": "open"},
        )

    assert response.status_code == 404


# --- Close-blocked-while-actions-open guard (design decision 4) -----------------


async def test_closing_is_blocked_while_an_action_is_open_then_unblocked(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        action_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/actions",
            headers=context.org_a_headers,
            json={"description": "Still outstanding"},
        )
        assert action_response.status_code == 201, action_response.text
        action_id = action_response.json()["id"]

        for to_status in ["investigate", "containment", "corrective_action", "verification"]:
            response = await client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": to_status},
            )
            assert response.status_code == 200, response.text

        blocked_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/transition",
            headers=context.org_a_headers,
            json={"to_status": "closed"},
        )
        assert blocked_response.status_code == 409

        complete_response = await client.patch(
            f"/api/v1/ncr/actions/{action_id}",
            headers=context.org_a_headers,
            json={"description": "Still outstanding", "status": "complete"},
        )
        assert complete_response.status_code == 200, complete_response.text

        unblocked_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/transition",
            headers=context.org_a_headers,
            json={"to_status": "closed"},
        )
        assert unblocked_response.status_code == 200, unblocked_response.text
        assert unblocked_response.json()["status"] == "closed"


async def test_concurrent_reopen_action_and_close_cannot_both_succeed(context: Context) -> None:
    """Independent review finding: create_action/update_action didn't lock the
    parent NCR row the same way transition_ncr's close guard does, so a concurrent
    action mutation and a close request could race -- the close guard's
    open-actions count could run and see zero right as an action flips back to
    open. Fixed by having create_action/update_action take the same per-NCR lock.
    Real concurrent requests against Postgres can exercise this -- kept as
    documentation of intended behaviour, not a guaranteed deterministic
    reproduction (same caveat as the other concurrency tests in this file)."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        action_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/actions",
            headers=context.org_a_headers,
            json={"description": "Will be reopened"},
        )
        assert action_response.status_code == 201, action_response.text
        action_id = action_response.json()["id"]

        for to_status in ["investigate", "containment", "corrective_action", "verification"]:
            response = await client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": to_status},
            )
            assert response.status_code == 200, response.text

        complete_response = await client.patch(
            f"/api/v1/ncr/actions/{action_id}",
            headers=context.org_a_headers,
            json={"description": "Will be reopened", "status": "complete"},
        )
        assert complete_response.status_code == 200, complete_response.text

        results = await asyncio.gather(
            client.patch(
                f"/api/v1/ncr/actions/{action_id}",
                headers=context.org_a_headers,
                json={"description": "Will be reopened", "status": "open"},
            ),
            client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": "closed"},
            ),
        )

        reopen_response, close_response = results

        final_ncr_response = await client.get(
            f"/api/v1/ncr/{ncr_id}", headers=context.org_a_headers
        )
        final_action_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/actions", headers=context.org_a_headers
        )
        final_action = final_action_response.json()["items"][0]
        # Whichever request reached the per-NCR lock first, exactly one of the two
        # valid orderings must hold -- the two must never disagree with each other:
        # (a) reopen won: the action is open and closing was correctly rejected;
        # (b) close won: the NCR is closed, the reopen was correctly rejected (an
        #     NCR's actions freeze once closed), and the action never changed.
        if reopen_response.status_code == 200:
            assert final_action["status"] == "open"
            assert close_response.status_code == 409
            assert final_ncr_response.json()["status"] != "closed"
        else:
            assert reopen_response.status_code == 409
            assert final_action["status"] == "complete"
            assert close_response.status_code == 200
            assert final_ncr_response.json()["status"] == "closed"


# --- Investigation tools -----------------------------------------------------------


async def test_get_investigation_tool_returns_default_when_not_started(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/five_why", headers=context.org_a_headers
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {}
    assert response.json()["id"] is None


async def test_get_investigation_tool_returns_404_for_another_organisations_ncr(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/five_why", headers=context.org_a_headers
        )

    assert response.status_code == 404


async def test_get_investigation_tool_rejects_an_invalid_tool_type(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/not-a-real-tool", headers=context.org_a_headers
        )

    assert response.status_code == 422


async def test_upsert_investigation_tool_creates_then_replaces_through_the_api(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        create_response = await client.put(
            f"/api/v1/ncr/{ncr_id}/tools/fishbone",
            headers=context.org_a_headers,
            json={"data": {"categories": ["Machine", "Method"]}},
        )
        assert create_response.status_code == 200, create_response.text
        assert create_response.json()["data"] == {"categories": ["Machine", "Method"]}
        tool_id = create_response.json()["id"]
        assert tool_id is not None

        replace_response = await client.put(
            f"/api/v1/ncr/{ncr_id}/tools/fishbone",
            headers=context.org_a_headers,
            json={"data": {"categories": ["Machine", "Method", "Material"]}},
        )
        assert replace_response.status_code == 200, replace_response.text
        assert replace_response.json()["id"] == tool_id
        assert replace_response.json()["data"] == {"categories": ["Machine", "Method", "Material"]}

        get_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/fishbone", headers=context.org_a_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"] == {"categories": ["Machine", "Method", "Material"]}

        # A different tool_type on the same NCR is independent.
        other_get_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/eight_d", headers=context.org_a_headers
        )
        assert other_get_response.status_code == 200
        assert other_get_response.json()["data"] == {}


async def test_upsert_investigation_tool_returns_404_for_another_organisations_ncr(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)

        response = await client.put(
            f"/api/v1/ncr/{ncr_id}/tools/ten_d",
            headers=context.org_a_headers,
            json={"data": {"team": "Should not be saved"}},
        )

    assert response.status_code == 404


async def test_upsert_investigation_tool_rejects_editing_a_closed_ncr(context: Context) -> None:
    """Independent security review found this slice had no equivalent to actions'
    frozen-once-closed rule -- a closed NCR's investigation worksheet could be
    silently rewritten after closure."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        create_response = await client.put(
            f"/api/v1/ncr/{ncr_id}/tools/five_why",
            headers=context.org_a_headers,
            json={"data": {"why_1": "Original"}},
        )
        assert create_response.status_code == 200, create_response.text

        for to_status in [
            "investigate",
            "containment",
            "corrective_action",
            "verification",
            "closed",
        ]:
            response = await client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": to_status},
            )
            assert response.status_code == 200, response.text

        rewrite_response = await client.put(
            f"/api/v1/ncr/{ncr_id}/tools/five_why",
            headers=context.org_a_headers,
            json={"data": {"why_1": "Tampered after closure"}},
        )
        assert rewrite_response.status_code == 409

        # Reads must still work on a closed NCR (e.g. for a future PDF export).
        get_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/tools/five_why", headers=context.org_a_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["data"] == {"why_1": "Original"}


# --- Attachments ---------------------------------------------------------------


async def test_attachment_lifecycle_and_cross_org_document_validation(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)

        org_b_document_id = await _create_document(client, context.org_b_headers)
        cross_org_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": org_b_document_id},
        )
        assert cross_org_response.status_code == 404

        document_id = await _create_document(client, context.org_a_headers)
        create_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": document_id, "description": "Defect photo"},
        )
        assert create_response.status_code == 201, create_response.text
        attachment_id = create_response.json()["id"]

        duplicate_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": document_id},
        )
        assert duplicate_response.status_code == 409

        list_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/attachments", headers=context.org_a_headers
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

        delete_response = await client.delete(
            f"/api/v1/ncr/{ncr_id}/attachments/{attachment_id}", headers=context.org_a_headers
        )
        assert delete_response.status_code == 204

        final_list_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/attachments", headers=context.org_a_headers
        )
        assert final_list_response.json()["total"] == 0


async def test_create_attachment_returns_404_for_another_organisations_ncr(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_raised_by_id = await _create_person(client, context.org_b_headers)
        ncr_id = await _create_ncr(client, context.org_b_headers, org_b_raised_by_id)
        document_id = await _create_document(client, context.org_a_headers)

        response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": document_id},
        )

    assert response.status_code == 404


async def test_attachments_are_frozen_once_the_ncr_is_closed(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        ncr_id = await _create_ncr(client, context.org_a_headers, raised_by_id)
        document_id = await _create_document(client, context.org_a_headers)

        create_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": document_id},
        )
        assert create_response.status_code == 201, create_response.text
        attachment_id = create_response.json()["id"]

        for to_status in [
            "investigate",
            "containment",
            "corrective_action",
            "verification",
            "closed",
        ]:
            response = await client.post(
                f"/api/v1/ncr/{ncr_id}/transition",
                headers=context.org_a_headers,
                json={"to_status": to_status},
            )
            assert response.status_code == 200, response.text

        another_document_id = await _create_document(client, context.org_a_headers)
        blocked_create_response = await client.post(
            f"/api/v1/ncr/{ncr_id}/attachments",
            headers=context.org_a_headers,
            json={"document_id": another_document_id},
        )
        assert blocked_create_response.status_code == 409

        blocked_delete_response = await client.delete(
            f"/api/v1/ncr/{ncr_id}/attachments/{attachment_id}", headers=context.org_a_headers
        )
        assert blocked_delete_response.status_code == 409

        # Reads must still work on a closed NCR.
        list_response = await client.get(
            f"/api/v1/ncr/{ncr_id}/attachments", headers=context.org_a_headers
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1


# --- Supplier NCR history --------------------------------------------------------


async def test_supplier_ncr_history_lists_only_that_suppliers_ncrs(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        raised_by_id = await _create_person(client, context.org_a_headers)
        supplier_id = await _create_supplier(client, context.org_a_headers)
        other_supplier_id = await _create_supplier(client, context.org_a_headers)

        await _create_ncr(
            client,
            context.org_a_headers,
            raised_by_id,
            type="supplier",
            supplier_id=supplier_id,
        )
        await _create_ncr(
            client,
            context.org_a_headers,
            raised_by_id,
            type="supplier",
            supplier_id=other_supplier_id,
        )
        await _create_ncr(client, context.org_a_headers, raised_by_id)

        response = await client.get(
            f"/api/v1/suppliers/{supplier_id}/ncr-history", headers=context.org_a_headers
        )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["supplier_id"] == supplier_id


async def test_supplier_ncr_history_returns_404_for_another_organisations_supplier(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_supplier_id = await _create_supplier(client, context.org_b_headers)

        response = await client.get(
            f"/api/v1/suppliers/{org_b_supplier_id}/ncr-history", headers=context.org_a_headers
        )

    assert response.status_code == 404
