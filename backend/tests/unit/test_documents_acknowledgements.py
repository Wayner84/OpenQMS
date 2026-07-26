"""Unit tests for app/modules/documents/service.py's acknowledgement functions
(SQLite for the DB side, a real tmp_path for the file side).
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


@pytest.fixture
async def user_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.models.user import User

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="reader@example.com",
            hashed_password="irrelevant",
            full_name="Reader",
        )
        session.add(user)
        await session.commit()
        return user.id


@pytest.fixture
async def other_user_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.models.user import User

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="reader2@example.com",
            hashed_password="irrelevant",
            full_name="Reader Two",
        )
        session.add(user)
        await session.commit()
        return user.id


async def _create_version(
    session_maker: SessionMaker, organisation_id: uuid.UUID, tmp_path: Path
) -> tuple[uuid.UUID, uuid.UUID]:
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
            upload=_FakeUpload("report.pdf", b"%PDF-1.7\nhello"),
            change_summary=None,
            created_by_id=None,
            uploads_dir=tmp_path,
        )
    return document.id, version.id


async def test_acknowledge_records_actor_and_timestamp(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import acknowledge_document_version

    document_id, version_id = await _create_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        acknowledgement = await acknowledge_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=user_id,
        )

    assert acknowledgement.document_version_id == version_id
    assert acknowledgement.acknowledged_by_id == user_id
    assert acknowledgement.acknowledged_at is not None


async def test_acknowledge_is_idempotent(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID, tmp_path: Path
) -> None:
    from app.modules.documents.service import acknowledge_document_version

    document_id, version_id = await _create_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        first = await acknowledge_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=user_id,
        )
    async with session_maker() as session:
        second = await acknowledge_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=user_id,
        )

    assert first.id == second.id


async def test_acknowledge_raises_not_found_for_cross_org_document(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    tmp_path: Path,
) -> None:
    from app.modules.documents.service import DocumentNotFoundError, acknowledge_document_version

    document_id, version_id = await _create_version(session_maker, other_organisation_id, tmp_path)

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await acknowledge_document_version(
                session,
                organisation_id=organisation_id,
                document_id=document_id,
                version_id=version_id,
                acknowledged_by_id=uuid.uuid4(),
            )


async def test_list_acknowledgements_returns_all_acknowledgers(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
    tmp_path: Path,
) -> None:
    from app.modules.documents.service import (
        acknowledge_document_version,
        list_document_version_acknowledgements,
    )

    document_id, version_id = await _create_version(session_maker, organisation_id, tmp_path)

    async with session_maker() as session:
        await acknowledge_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=user_id,
        )
    async with session_maker() as session:
        await acknowledge_document_version(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=other_user_id,
        )

    async with session_maker() as session:
        acknowledgements, total = await list_document_version_acknowledgements(
            session,
            organisation_id=organisation_id,
            document_id=document_id,
            version_id=version_id,
            limit=50,
            offset=0,
        )

    assert total == 2
    assert {a.acknowledged_by_id for a in acknowledgements} == {user_id, other_user_id}


async def test_list_acknowledgements_raises_not_found_for_cross_org_document(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    tmp_path: Path,
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        list_document_version_acknowledgements,
    )

    document_id, version_id = await _create_version(session_maker, other_organisation_id, tmp_path)

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await list_document_version_acknowledgements(
                session,
                organisation_id=organisation_id,
                document_id=document_id,
                version_id=version_id,
                limit=50,
                offset=0,
            )
