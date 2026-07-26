"""Unit tests for app/modules/documents/upload_policy.py (SQLite)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.documents.models  # noqa: F401
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


async def test_get_upload_policy_falls_back_to_default_when_missing(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.upload_policy import (
        DEFAULT_ALLOWED_EXTENSIONS,
        DEFAULT_MAX_SIZE_MB,
        get_upload_policy,
    )

    async with session_maker() as session:
        policy = await get_upload_policy(session, organisation_id=organisation_id)

    assert policy.allowed_extensions == DEFAULT_ALLOWED_EXTENSIONS
    assert policy.max_size_bytes == DEFAULT_MAX_SIZE_MB * 1024 * 1024


async def test_get_upload_policy_silently_drops_extensions_unknown_to_the_backend(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    """An operator-configured extension the backend has no CONTENT_TYPE_BY_EXTENSION
    entry for must never be accepted -- it would otherwise crash the upload path
    with a KeyError deeper in create_document_version, not fail cleanly."""
    from app.models.configuration import Configuration
    from app.modules.documents.upload_policy import UPLOAD_POLICY_KEY, get_upload_policy

    async with session_maker() as session:
        session.add(
            Configuration(
                organisation_id=organisation_id,
                key=UPLOAD_POLICY_KEY,
                value={"allowed_extensions": [".pdf", ".exe", ".sh"], "max_size_mb": 10},
            )
        )
        await session.commit()

    async with session_maker() as session:
        policy = await get_upload_policy(session, organisation_id=organisation_id)

    assert policy.allowed_extensions == frozenset({".pdf"})
    assert policy.max_size_bytes == 10 * 1024 * 1024
