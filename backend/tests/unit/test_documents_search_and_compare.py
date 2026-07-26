"""Unit tests for app/modules/documents/service.py's search/filtering
(list_documents) and version comparison (compare_document_versions) additions.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


class _FakeUpload:
    def __init__(self, filename: str, data: bytes) -> None:
        self.filename: str | None = filename
        self._data = data
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.documents.models  # noqa: F401
    import app.modules.people.models  # noqa: F401
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


# --- search/filtering ----------------------------------------------------------


async def test_list_documents_search_matches_title_and_number(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document, list_documents

    async with session_maker() as session:
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Welding Procedure",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        by_title, total_title = await list_documents(
            session,
            organisation_id=organisation_id,
            category_id=None,
            status=None,
            owner_id=None,
            search="quality",
            tag=None,
            limit=50,
            offset=0,
        )
        by_number, total_number = await list_documents(
            session,
            organisation_id=organisation_id,
            category_id=None,
            status=None,
            owner_id=None,
            search="doc-0002",
            tag=None,
            limit=50,
            offset=0,
        )

    assert total_title == 1
    assert by_title[0].title == "Quality Manual"
    assert total_number == 1
    assert by_number[0].title == "Welding Procedure"


async def test_list_documents_filters_by_tag(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document, create_tag, list_documents

    async with session_maker() as session:
        controlled_tag = await create_tag(
            session, organisation_id=organisation_id, name="controlled"
        )
        await create_tag(session, organisation_id=organisation_id, name="draft-only")
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=None,
            owner_id=None,
            tag_ids=[controlled_tag.id],
            created_by_id=None,
        )
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Uncontrolled Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        documents, total = await list_documents(
            session,
            organisation_id=organisation_id,
            category_id=None,
            status=None,
            owner_id=None,
            search=None,
            tag="controlled",
            limit=50,
            offset=0,
        )

    assert total == 1
    assert documents[0].title == "Quality Manual"


async def test_list_documents_search_and_tag_combine(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document, create_tag, list_documents

    async with session_maker() as session:
        tag = await create_tag(session, organisation_id=organisation_id, name="controlled")
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=None,
            owner_id=None,
            tag_ids=[tag.id],
            created_by_id=None,
        )
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        documents, total = await list_documents(
            session,
            organisation_id=organisation_id,
            category_id=None,
            status=None,
            owner_id=None,
            search="quality",
            tag="controlled",
            limit=50,
            offset=0,
        )

    assert total == 1
    assert documents[0].title == "Quality Manual"


# --- version comparison ---------------------------------------------------------


async def test_compare_versions_reports_text_diff_for_text_files(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("notes.txt", b"line one\nline two\n"),
            change_summary="Initial",
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("notes.txt", b"line one\nline TWO\nline three\n"),
            change_summary="Revised",
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        comparison = await compare_document_versions(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            uploads_dir=tmp_path,
        )

    assert comparison.checksum_changed is True
    assert comparison.text_diff is not None
    diff_text = "".join(comparison.text_diff)
    assert "-line two" in diff_text
    assert "+line TWO" in diff_text
    assert "+line three" in diff_text


async def test_compare_versions_reports_binary_changed_for_non_text_files(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Drawing",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("drawing.pdf", b"%PDF-1.7\nrevision one"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("drawing.pdf", b"%PDF-1.7\nrevision two, longer content"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        comparison = await compare_document_versions(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            uploads_dir=tmp_path,
        )

    assert comparison.checksum_changed is True
    assert comparison.text_diff is None


async def test_compare_versions_reports_unchanged_checksum_for_identical_content(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("notes.txt", b"identical content\n"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("notes.txt", b"identical content\n"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        comparison = await compare_document_versions(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            uploads_dir=tmp_path,
        )

    assert comparison.checksum_changed is False
    assert comparison.text_diff == []


async def test_compare_versions_raises_not_found_for_a_version_of_a_different_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    """A version genuinely belonging to a different document (even within the same
    organisation) must 404, not be silently compared against the wrong document."""
    from app.modules.documents.service import (
        DocumentVersionNotFoundError,
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document_a = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc A",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        document_b = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc B",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_of_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_a.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_of_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_b.id,
            upload=_FakeUpload("b.txt", b"hello again"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentVersionNotFoundError):
            await compare_document_versions(
                session,
                organisation_id=organisation_id,
                document_id=document_a.id,
                version_a_id=version_of_a.id,
                version_b_id=version_of_b.id,
                uploads_dir=tmp_path,
            )


async def test_compare_versions_skips_text_diff_above_the_size_cap(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two large text-comparable files fall back to checksum-only, per the
    MAX_TEXT_DIFF_BYTES guard added after an independent review flagged
    unbounded in-memory diffing as a resource-exhaustion risk."""
    from app.modules.documents import service as documents_service
    from app.modules.documents.service import (
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Big Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("a.txt", b"a" * 100),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("b.txt", b"b" * 200),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    monkeypatch.setattr(documents_service, "MAX_TEXT_DIFF_BYTES", 50)
    async with session_maker() as session:
        comparison = await compare_document_versions(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            uploads_dir=tmp_path,
        )

    assert comparison.checksum_changed is True
    assert comparison.text_diff is None


async def test_compare_versions_raises_clear_error_when_a_file_is_missing(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        VersionFileMissingError,
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Notes",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("b.txt", b"hello again"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    # Simulate an operational data-integrity problem: the file is gone from disk
    # even though the DB row still references it.
    (tmp_path / version_a.storage_key).unlink()

    async with session_maker() as session:
        with pytest.raises(VersionFileMissingError):
            await compare_document_versions(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                version_a_id=version_a.id,
                version_b_id=version_b.id,
                uploads_dir=tmp_path,
            )


async def test_compare_versions_raises_not_found_for_cross_org(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        compare_document_versions,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        other_org = Organisation(name="Other Org", slug="other")
        session.add(other_org)
        await session.commit()
        other_org_id = other_org.id

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=other_org_id,
            title="Other Org Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        version_a = await create_document_version(
            session,
            organisation_id=other_org_id,
            document_id=document.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        version_b = await create_document_version(
            session,
            organisation_id=other_org_id,
            document_id=document.id,
            upload=_FakeUpload("b.txt", b"hello again"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await compare_document_versions(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                version_a_id=version_a.id,
                version_b_id=version_b.id,
                uploads_dir=tmp_path,
            )
