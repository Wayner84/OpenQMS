"""Unit tests for app/modules/documents/service.py's version upload/lookup
functions (SQLite for the DB side, a real tmp_path for the file side).
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


@pytest.fixture
async def other_organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Other Organisation", slug="other")
        session.add(org)
        await session.commit()
        return org.id


async def test_create_document_version_sets_metadata_from_validated_extension(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.models import DocumentVersionStatus
    from app.modules.documents.service import create_document, create_document_version

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="SOP 1",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        version = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("../../etc/passwd.pdf", b"%PDF-1.7\nhello"),
            change_summary="Initial draft",
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    assert version.version_number == 1
    assert version.content_type == "application/pdf"
    assert version.status == DocumentVersionStatus.DRAFT
    assert version.original_filename == "passwd.pdf"  # sanitised, never a real path
    assert "/" not in version.original_filename
    assert version.storage_key.startswith(f"{organisation_id}/{document.id}/")

    stored_path = tmp_path / version.storage_key
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"%PDF-1.7\nhello"


async def test_create_document_version_increments_version_number(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import create_document, create_document_version

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="SOP 1",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        first = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    async with session_maker() as session:
        second = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            upload=_FakeUpload("b.txt", b"hello again"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    assert first.version_number == 1
    assert second.version_number == 2


async def test_create_document_version_rejects_disallowed_extension(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import create_document, create_document_version
    from app.modules.documents.storage import UnsupportedFileTypeError

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="SOP 1",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(UnsupportedFileTypeError):
            await create_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                upload=_FakeUpload("malware.exe", b"MZ\x90\x00"),
                change_summary=None,
                created_by_id=None,
                uploads_dir=tmp_path,
            )


async def test_create_document_version_rejects_wrong_signature(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import create_document, create_document_version
    from app.modules.documents.storage import InvalidFileSignatureError

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="SOP 1",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(InvalidFileSignatureError):
            await create_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                # An .exe's real signature, relabelled with a .pdf extension.
                upload=_FakeUpload("fake.pdf", b"MZ\x90\x00\x03\x00\x00\x00"),
                change_summary=None,
                created_by_id=None,
                uploads_dir=tmp_path,
            )


async def test_create_document_version_raises_not_found_for_cross_org_document(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    tmp_path: Path,
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        create_document,
        create_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=other_organisation_id,
            title="Other Org Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await create_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                upload=_FakeUpload("a.txt", b"hello"),
                change_summary=None,
                created_by_id=None,
                uploads_dir=tmp_path,
            )


async def test_get_document_version_raises_not_found_for_cross_org_document(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    tmp_path: Path,
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        create_document,
        create_document_version,
        get_document_version,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=other_organisation_id,
            title="Other Org Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        version = await create_document_version(
            session,
            organisation_id=other_organisation_id,
            document_id=document.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await get_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                version_id=version.id,
            )


async def test_get_document_version_raises_not_found_for_version_of_another_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import (
        DocumentVersionNotFoundError,
        create_document,
        create_document_version,
        get_document_version,
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
        version_of_b = await create_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_b.id,
            upload=_FakeUpload("a.txt", b"hello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentVersionNotFoundError):
            await get_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document_a.id,
                version_id=version_of_b.id,
            )
