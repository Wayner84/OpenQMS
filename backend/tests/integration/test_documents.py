"""Integration tests for the Document Management module's core schema (categories,
tags, documents) against real PostgreSQL.

Follows the tests/integration/test_people.py pattern. Covers the Milestone 2 plan's
hard acceptance criteria for this slice: organisation isolation, server-generated
numbering (seeded via the migration's data seed), category delete guards, cascading
tag delete, and owner/tag/category validation.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, update
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
    org_a_id: uuid.UUID
    database_url: str


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
async def context(
    database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[Context]:
    import app.core.config as config_module
    import app.core.db as db_module
    from app.core.security import hash_password
    from app.main import create_app
    from app.models.configuration import Configuration
    from app.models.organisation import Organisation
    from app.models.user import User, UserRole
    from app.modules.documents.models import (
        Document,
        DocumentAcknowledgement,
        DocumentApproval,
        DocumentCategory,
        DocumentTag,
        DocumentTagLink,
        DocumentVersion,
    )
    from app.modules.documents.numbering import NUMBERING_SCHEME_KEY
    from app.modules.documents.upload_policy import (
        DEFAULT_ALLOWED_EXTENSIONS,
        DEFAULT_MAX_SIZE_MB,
        UPLOAD_POLICY_KEY,
    )
    from app.modules.ncr.models import Ncr

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-secret-key")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    config_module.get_settings.cache_clear()
    db_module.get_session_factory.cache_clear()

    suffix = uuid.uuid4().hex[:8]
    engine = create_async_engine(database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        org_a = (
            await session.execute(select(Organisation).where(Organisation.slug == "default"))
        ).scalar_one()

        # Shared, persistent dev database: reset the default organisation's document
        # rows and numbering sequence so earlier local runs don't affect these
        # assertions (mirrors tests/integration/test_people.py's own reset).
        # ncr_attachments.document_id references documents.id, so any leftover NCR
        # row (which cascade-deletes its attachments) must be cleared first or the
        # Document delete below fails on a foreign key violation.
        await session.execute(delete(Ncr).where(Ncr.organisation_id == org_a.id))
        await session.execute(
            delete(DocumentTagLink).where(
                DocumentTagLink.document_id.in_(
                    select(Document.id).where(Document.organisation_id == org_a.id)
                )
            )
        )
        await session.execute(
            delete(DocumentApproval).where(
                DocumentApproval.document_version_id.in_(
                    select(DocumentVersion.id).where(
                        DocumentVersion.document_id.in_(
                            select(Document.id).where(Document.organisation_id == org_a.id)
                        )
                    )
                )
            )
        )
        await session.execute(
            delete(DocumentAcknowledgement).where(
                DocumentAcknowledgement.document_version_id.in_(
                    select(DocumentVersion.id).where(
                        DocumentVersion.document_id.in_(
                            select(Document.id).where(Document.organisation_id == org_a.id)
                        )
                    )
                )
            )
        )
        # documents.current_version_id references document_versions.id -- null it
        # out first so the version rows below can actually be deleted.
        await session.execute(
            update(Document)
            .where(Document.organisation_id == org_a.id)
            .values(current_version_id=None)
        )
        await session.execute(
            delete(DocumentVersion).where(
                DocumentVersion.document_id.in_(
                    select(Document.id).where(Document.organisation_id == org_a.id)
                )
            )
        )
        await session.execute(delete(Document).where(Document.organisation_id == org_a.id))
        await session.execute(delete(DocumentTag).where(DocumentTag.organisation_id == org_a.id))
        await session.execute(
            delete(DocumentCategory).where(DocumentCategory.organisation_id == org_a.id)
        )
        await session.execute(delete(User).where(User.organisation_id == org_a.id))
        await session.execute(
            delete(Configuration).where(
                Configuration.organisation_id == org_a.id, Configuration.key == NUMBERING_SCHEME_KEY
            )
        )
        session.add(
            Configuration(
                organisation_id=org_a.id,
                key=NUMBERING_SCHEME_KEY,
                value={"prefix": "DOC", "separator": "-", "padding": 4, "next_sequence": 1},
            )
        )
        # Also reset the upload policy to its default -- a test may seed a
        # restrictive override (see test_upload_rejects_oversized_file_...) and this
        # is a shared, persistent dev database, not a per-test-run disposable one.
        await session.execute(
            delete(Configuration).where(
                Configuration.organisation_id == org_a.id, Configuration.key == UPLOAD_POLICY_KEY
            )
        )
        session.add(
            Configuration(
                organisation_id=org_a.id,
                key=UPLOAD_POLICY_KEY,
                value={
                    "allowed_extensions": sorted(DEFAULT_ALLOWED_EXTENSIONS),
                    "max_size_mb": DEFAULT_MAX_SIZE_MB,
                },
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
            org_a_id=org_a.id,
            database_url=database_url,
        )
    finally:
        await db_module.get_session_factory().engine.dispose()

        cleanup_engine = create_async_engine(database_url)
        cleanup_session_maker = async_sessionmaker(cleanup_engine, expire_on_commit=False)
        async with cleanup_session_maker() as cleanup_session:
            await cleanup_session.execute(
                delete(DocumentTagLink).where(
                    DocumentTagLink.document_id.in_(
                        select(Document.id).where(Document.organisation_id == org_b.id)
                    )
                )
            )
            await cleanup_session.execute(
                delete(DocumentApproval).where(
                    DocumentApproval.document_version_id.in_(
                        select(DocumentVersion.id).where(
                            DocumentVersion.document_id.in_(
                                select(Document.id).where(Document.organisation_id == org_b.id)
                            )
                        )
                    )
                )
            )
            await cleanup_session.execute(
                delete(DocumentAcknowledgement).where(
                    DocumentAcknowledgement.document_version_id.in_(
                        select(DocumentVersion.id).where(
                            DocumentVersion.document_id.in_(
                                select(Document.id).where(Document.organisation_id == org_b.id)
                            )
                        )
                    )
                )
            )
            await cleanup_session.execute(
                update(Document)
                .where(Document.organisation_id == org_b.id)
                .values(current_version_id=None)
            )
            await cleanup_session.execute(
                delete(DocumentVersion).where(
                    DocumentVersion.document_id.in_(
                        select(Document.id).where(Document.organisation_id == org_b.id)
                    )
                )
            )
            await cleanup_session.execute(
                delete(Document).where(Document.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(DocumentTag).where(DocumentTag.organisation_id == org_b.id)
            )
            await cleanup_session.execute(
                delete(DocumentCategory).where(DocumentCategory.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(User).where(User.organisation_id == org_b.id))
            await cleanup_session.execute(
                delete(Configuration).where(Configuration.organisation_id == org_b.id)
            )
            await cleanup_session.execute(delete(Organisation).where(Organisation.id == org_b.id))
            await cleanup_session.commit()
        await cleanup_engine.dispose()


async def test_create_document_generates_sequential_numbers(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "Quality Manual"}
        )
        second = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["number"] == "DOC-0001"
    assert second.json()["number"] == "DOC-0002"
    assert first.json()["status"] == "draft"
    assert first.json()["created_by_id"] == str(context.org_a_user_id)


async def test_get_document_returns_404_for_another_organisations_document(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Doc"}
        )
        document_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )

    assert response.status_code == 404


async def test_create_document_with_category_and_tags(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_response = await client.post(
            "/api/v1/document-categories", headers=context.org_a_headers, json={"name": "Quality"}
        )
        category_id = category_response.json()["id"]
        tag_response = await client.post(
            "/api/v1/document-tags", headers=context.org_a_headers, json={"name": "controlled"}
        )
        tag_id = tag_response.json()["id"]

        response = await client.post(
            "/api/v1/documents",
            headers=context.org_a_headers,
            json={"title": "SOP 1", "category_id": category_id, "tag_ids": [tag_id]},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["category_id"] == category_id
    assert [t["id"] for t in body["tags"]] == [tag_id]


async def test_create_category_requires_admin(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-cat@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-cat@example.com", "member-password")

        response = await client.post(
            "/api/v1/document-categories", headers=member_headers, json={"name": "Quality"}
        )

    assert response.status_code == 403


async def test_update_category_returns_422_for_a_cyclical_parent(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        parent_response = await client.post(
            "/api/v1/document-categories", headers=context.org_a_headers, json={"name": "A"}
        )
        parent_id = parent_response.json()["id"]
        child_response = await client.post(
            "/api/v1/document-categories",
            headers=context.org_a_headers,
            json={"name": "B", "parent_category_id": parent_id},
        )
        child_id = child_response.json()["id"]

        response = await client.patch(
            f"/api/v1/document-categories/{parent_id}",
            headers=context.org_a_headers,
            json={"name": "A", "parent_category_id": child_id},
        )

    assert response.status_code == 422


async def test_concurrent_reciprocal_reparenting_cannot_both_succeed(context: Context) -> None:
    """Independent review finding: without a database lock serialising category-tree
    mutations per organisation, two concurrent updates -- A.parent := B and
    B.parent := A -- can each read the pre-update tree in `_assert_no_category_cycle`
    before the other commits its write, so both see "no cycle" and both succeed,
    together creating a cycle that neither update alone would have passed. Only real
    concurrent transactions against a database that actually enforces row locks
    (Postgres) can exercise this -- SQLite's unit tests can't, since SQLite has no
    real row-level locking and is single-writer regardless. With the fix
    (service._lock_category_tree), the second transaction to reach the lock must
    wait for the first to commit, so it observes the already-updated tree and
    correctly rejects its own update as cyclical: exactly one of the two requests
    succeeds."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response_a = await client.post(
            "/api/v1/document-categories", headers=context.org_a_headers, json={"name": "A"}
        )
        response_b = await client.post(
            "/api/v1/document-categories", headers=context.org_a_headers, json={"name": "B"}
        )
        category_a_id = response_a.json()["id"]
        category_b_id = response_b.json()["id"]

        results = await asyncio.gather(
            client.patch(
                f"/api/v1/document-categories/{category_a_id}",
                headers=context.org_a_headers,
                json={"name": "A", "parent_category_id": category_b_id},
            ),
            client.patch(
                f"/api/v1/document-categories/{category_b_id}",
                headers=context.org_a_headers,
                json={"name": "B", "parent_category_id": category_a_id},
            ),
        )

    assert sorted(response.status_code for response in results) == [200, 422]


async def test_delete_category_returns_409_when_referenced_by_a_document(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        category_response = await client.post(
            "/api/v1/document-categories", headers=context.org_a_headers, json={"name": "Quality"}
        )
        category_id = category_response.json()["id"]
        await client.post(
            "/api/v1/documents",
            headers=context.org_a_headers,
            json={"title": "SOP 1", "category_id": category_id},
        )

        response = await client.delete(
            f"/api/v1/document-categories/{category_id}", headers=context.org_a_headers
        )

    assert response.status_code == 409


async def test_delete_tag_cascades_and_is_removed_from_documents(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tag_response = await client.post(
            "/api/v1/document-tags", headers=context.org_a_headers, json={"name": "controlled"}
        )
        tag_id = tag_response.json()["id"]
        create_response = await client.post(
            "/api/v1/documents",
            headers=context.org_a_headers,
            json={"title": "SOP 1", "tag_ids": [tag_id]},
        )
        document_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/document-tags/{tag_id}", headers=context.org_a_headers
        )
        get_response = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )

    assert delete_response.status_code == 204
    assert get_response.json()["tags"] == []


async def test_soft_deleted_document_is_excluded_from_list_and_get(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        delete_response = await client.delete(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )
        get_response = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )
        list_response = await client.get("/api/v1/documents", headers=context.org_a_headers)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert all(item["id"] != document_id for item in list_response.json()["items"])


async def test_delete_document_requires_admin(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-del@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-del@example.com", "member-password")

        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.delete(f"/api/v1/documents/{document_id}", headers=member_headers)

    assert response.status_code == 403


async def test_create_document_rejects_cross_org_category(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        org_b_category_response = await client.post(
            "/api/v1/document-categories", headers=context.org_b_headers, json={"name": "Org B Cat"}
        )
        org_b_category_id = org_b_category_response.json()["id"]

        response = await client.post(
            "/api/v1/documents",
            headers=context.org_a_headers,
            json={"title": "SOP 1", "category_id": org_b_category_id},
        )

    assert response.status_code == 404


async def test_list_document_versions_is_empty_for_a_new_document(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{document_id}/versions", headers=context.org_a_headers
        )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_upload_download_roundtrip_returns_correct_bytes_and_headers(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello world", "application/pdf")},
            data={"change_summary": "Initial draft"},
        )
        assert upload_response.status_code == 201, upload_response.text
        version_body = upload_response.json()
        assert version_body["version_number"] == 1
        assert version_body["content_type"] == "application/pdf"
        assert version_body["original_filename"] == "report.pdf"
        assert "storage_key" not in version_body
        version_id = version_body["id"]

        download_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/download",
            headers=context.org_a_headers,
        )

    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.7\nhello world"
    assert download_response.headers["content-type"] == "application/pdf"
    assert "attachment" in download_response.headers["content-disposition"]
    assert "report.pdf" in download_response.headers["content-disposition"]
    assert download_response.headers["x-content-type-options"] == "nosniff"


async def test_non_admin_member_can_upload_and_download_a_version(context: Context) -> None:
    """Per the plan's permissions summary, upload/download is any-active-user, not
    admin-only -- only approve/reject/retire/delete are admin-gated."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-upload@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-upload@example.com", "member-password")

        create_response = await client.post(
            "/api/v1/documents", headers=member_headers, json={"title": "SOP 1"}
        )
        assert create_response.status_code == 201, create_response.text
        document_id = create_response.json()["id"]

        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=member_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        assert upload_response.status_code == 201, upload_response.text
        version_id = upload_response.json()["id"]

        download_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/download",
            headers=member_headers,
        )

    assert download_response.status_code == 200
    assert download_response.content == b"%PDF-1.7\nhello"


async def test_preview_returns_inline_for_pdf_and_415_for_non_previewable_type(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        pdf_upload = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        pdf_version_id = pdf_upload.json()["id"]

        txt_upload = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("notes.txt", b"plain text notes", "text/plain")},
        )
        txt_version_id = txt_upload.json()["id"]

        pdf_preview = await client.get(
            f"/api/v1/documents/{document_id}/versions/{pdf_version_id}/preview",
            headers=context.org_a_headers,
        )
        txt_preview = await client.get(
            f"/api/v1/documents/{document_id}/versions/{txt_version_id}/preview",
            headers=context.org_a_headers,
        )

    assert pdf_preview.status_code == 200
    assert "inline" in pdf_preview.headers["content-disposition"]
    assert txt_preview.status_code == 415


async def test_download_returns_404_for_another_organisations_document_version(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Doc"}
        )
        document_id = create_response.json()["id"]
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_b_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        version_id = upload_response.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/download",
            headers=context.org_a_headers,
        )

    assert response.status_code == 404


async def test_upload_rejects_disallowed_extension(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        )

    assert response.status_code == 422


async def test_upload_rejects_content_that_does_not_match_its_extension(context: Context) -> None:
    """A file relabelled with a .pdf extension but containing an .exe's real
    signature must be rejected -- the backend checks the file's own bytes, never
    just the client-declared extension/Content-Type."""
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("fake.pdf", b"MZ\x90\x00\x03\x00\x00\x00", "application/pdf")},
        )

    assert response.status_code == 422


async def test_upload_rejects_oversized_file_per_a_seeded_small_policy(context: Context) -> None:
    """Seeds a tiny max_size_mb policy for org A so the test doesn't need to send a
    real 50 MB payload to exercise the default limit."""
    from app.models.configuration import Configuration
    from app.modules.documents.upload_policy import UPLOAD_POLICY_KEY

    engine = create_async_engine(context.database_url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            delete(Configuration).where(
                Configuration.organisation_id == context.org_a_id,
                Configuration.key == UPLOAD_POLICY_KEY,
            )
        )
        session.add(
            Configuration(
                organisation_id=context.org_a_id,
                key=UPLOAD_POLICY_KEY,
                value={"allowed_extensions": [".txt"], "max_size_mb": 1},
            )
        )
        await session.commit()
    await engine.dispose()

    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("big.txt", b"x" * (2 * 1024 * 1024), "text/plain")},
        )

    assert response.status_code == 413


async def test_upload_sanitises_a_path_traversal_filename(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("../../etc/passwd.txt", b"not actually /etc/passwd", "text/plain")},
        )

    assert response.status_code == 201, response.text
    assert response.json()["original_filename"] == "passwd.txt"
    assert "/" not in response.json()["original_filename"]
    assert ".." not in response.json()["original_filename"]


async def test_documents_and_categories_require_authentication(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        documents_response = await client.get("/api/v1/documents")
        categories_response = await client.get("/api/v1/document-categories")
        tags_response = await client.get("/api/v1/document-tags")

    assert documents_response.status_code == 401
    assert categories_response.status_code == 401
    assert tags_response.status_code == 401


async def _upload_and_submit(client: AsyncClient, headers: dict[str, str], document_id: str) -> str:
    upload_response = await client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=headers,
        files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
    )
    version_id = upload_response.json()["id"]
    submit_response = await client.post(
        f"/api/v1/documents/{document_id}/versions/{version_id}/submit-for-approval",
        headers=headers,
    )
    assert submit_response.status_code == 200, submit_response.text
    return str(version_id)


async def test_full_approval_workflow_supersedes_the_previous_version(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        first_version_id = await _upload_and_submit(client, context.org_a_headers, document_id)
        approve_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{first_version_id}/approve",
            headers=context.org_a_headers,
            json={"comments": "Looks good"},
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["status"] == "approved"

        document_after_first_approval = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )
        assert document_after_first_approval.json()["status"] == "approved"
        assert document_after_first_approval.json()["current_version_id"] == first_version_id

        second_version_id = await _upload_and_submit(client, context.org_a_headers, document_id)
        second_approve_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{second_version_id}/approve",
            headers=context.org_a_headers,
            json={},
        )
        assert second_approve_response.status_code == 200, second_approve_response.text

        first_version_after = await client.get(
            f"/api/v1/documents/{document_id}/versions", headers=context.org_a_headers
        )
        by_id = {item["id"]: item for item in first_version_after.json()["items"]}
        document_final = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )

    assert by_id[first_version_id]["status"] == "obsolete"
    assert by_id[second_version_id]["status"] == "approved"
    assert document_final.json()["current_version_id"] == second_version_id


async def test_reject_requires_admin_and_a_comment(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-reject@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-reject@example.com", "member-password")

        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]
        version_id = await _upload_and_submit(client, member_headers, document_id)

        member_reject_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/reject",
            headers=member_headers,
            json={"comments": "Not ready"},
        )
        no_comment_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/reject",
            headers=context.org_a_headers,
            json={"comments": ""},
        )
        reject_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/reject",
            headers=context.org_a_headers,
            json={"comments": "Missing a signature page"},
        )

        document_after = await client.get(
            f"/api/v1/documents/{document_id}", headers=context.org_a_headers
        )

    assert member_reject_response.status_code == 403
    assert no_comment_response.status_code == 422
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["status"] == "rejected"
    assert document_after.json()["status"] == "draft"


async def test_approve_returns_409_for_a_version_not_in_review(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        version_id = upload_response.json()["id"]

        response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/approve",
            headers=context.org_a_headers,
            json={},
        )

    assert response.status_code == 409


async def test_retire_document_requires_admin(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-retire@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-retire@example.com", "member-password")

        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]

        member_response2 = await client.post(
            f"/api/v1/documents/{document_id}/obsolete", headers=member_headers
        )
        admin_response = await client.post(
            f"/api/v1/documents/{document_id}/obsolete", headers=context.org_a_headers
        )

    assert member_response2.status_code == 403
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.json()["status"] == "obsolete"


async def test_workflow_endpoints_return_404_for_another_organisations_document(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Doc"}
        )
        document_id = create_response.json()["id"]
        version_id = await _upload_and_submit(client, context.org_b_headers, document_id)

        approve_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/approve",
            headers=context.org_a_headers,
            json={},
        )
        reject_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/reject",
            headers=context.org_a_headers,
            json={"comments": "no"},
        )
        obsolete_response = await client.post(
            f"/api/v1/documents/{document_id}/obsolete", headers=context.org_a_headers
        )

    assert approve_response.status_code == 404
    assert reject_response.status_code == 404
    assert obsolete_response.status_code == 404


async def test_acknowledge_is_idempotent_and_listable(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        version_id = upload_response.json()["id"]

        first_ack = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledge",
            headers=context.org_a_headers,
        )
        second_ack = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledge",
            headers=context.org_a_headers,
        )
        list_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledgements",
            headers=context.org_a_headers,
        )

    assert first_ack.status_code == 200, first_ack.text
    assert second_ack.status_code == 200, second_ack.text
    assert first_ack.json()["id"] == second_ack.json()["id"]
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["acknowledged_by_id"] == str(context.org_a_user_id)


async def test_a_member_can_acknowledge_and_a_different_member_sees_it_listed(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        member_response = await client.post(
            "/api/v1/users",
            headers=context.org_a_headers,
            json={
                "email": "member-ack@example.com",
                "full_name": "Member",
                "password": "member-password",
                "role": "member",
            },
        )
        assert member_response.status_code == 201, member_response.text
        member_headers = await _login(context.app, "member-ack@example.com", "member-password")

        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "SOP 1"}
        )
        document_id = create_response.json()["id"]
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        version_id = upload_response.json()["id"]

        ack_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledge",
            headers=member_headers,
        )
        list_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledgements",
            headers=context.org_a_headers,
        )

    assert ack_response.status_code == 200, ack_response.text
    assert list_response.json()["total"] == 1


async def test_acknowledge_returns_404_for_another_organisations_document(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Doc"}
        )
        document_id = create_response.json()["id"]
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_b_headers,
            files={"file": ("report.pdf", b"%PDF-1.7\nhello", "application/pdf")},
        )
        version_id = upload_response.json()["id"]

        ack_response = await client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledge",
            headers=context.org_a_headers,
        )
        list_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_id}/acknowledgements",
            headers=context.org_a_headers,
        )

    assert ack_response.status_code == 404
    assert list_response.status_code == 404


async def test_search_and_tag_filter_documents(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tag_response = await client.post(
            "/api/v1/document-tags", headers=context.org_a_headers, json={"name": "controlled"}
        )
        tag_id = tag_response.json()["id"]

        await client.post(
            "/api/v1/documents",
            headers=context.org_a_headers,
            json={"title": "Quality Manual", "tag_ids": [tag_id]},
        )
        await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "Welding Procedure"}
        )

        search_response = await client.get(
            "/api/v1/documents", headers=context.org_a_headers, params={"search": "quality"}
        )
        tag_filter_response = await client.get(
            "/api/v1/documents", headers=context.org_a_headers, params={"tag": "controlled"}
        )

    assert search_response.status_code == 200
    assert [item["title"] for item in search_response.json()["items"]] == ["Quality Manual"]
    assert tag_filter_response.status_code == 200
    assert [item["title"] for item in tag_filter_response.json()["items"]] == ["Quality Manual"]


async def test_compare_versions_through_http(context: Context) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_a_headers, json={"title": "Notes"}
        )
        document_id = create_response.json()["id"]

        version_a_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("notes.txt", b"line one\nline two\n", "text/plain")},
        )
        version_a_id = version_a_response.json()["id"]
        version_b_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_a_headers,
            files={"file": ("notes.txt", b"line one\nline THREE\n", "text/plain")},
        )
        version_b_id = version_b_response.json()["id"]

        compare_response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_a_id}/compare/{version_b_id}",
            headers=context.org_a_headers,
        )

    assert compare_response.status_code == 200, compare_response.text
    body = compare_response.json()
    assert body["checksum_changed"] is True
    assert body["text_diff"] is not None
    assert any("line THREE" in line for line in body["text_diff"])
    assert "storage_key" not in body["version_a"]
    assert "storage_key" not in body["version_b"]


async def test_compare_versions_returns_404_for_another_organisations_document(
    context: Context,
) -> None:
    transport = ASGITransport(app=context.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/documents", headers=context.org_b_headers, json={"title": "Org B Doc"}
        )
        document_id = create_response.json()["id"]
        version_a_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_b_headers,
            files={"file": ("a.txt", b"hello", "text/plain")},
        )
        version_b_response = await client.post(
            f"/api/v1/documents/{document_id}/versions",
            headers=context.org_b_headers,
            files={"file": ("b.txt", b"hello again", "text/plain")},
        )

        response = await client.get(
            f"/api/v1/documents/{document_id}/versions/{version_a_response.json()['id']}"
            f"/compare/{version_b_response.json()['id']}",
            headers=context.org_a_headers,
        )

    assert response.status_code == 404
