"""Unit tests for app/modules/documents/numbering.py (SQLite).

Per the Milestone 2 plan's "Configurable numbering" section: numbers are generated
from an organisation-scoped `configuration` row, never a hard-coded prefix, and the
sequence is seeded lazily with a conservative default if the row is missing.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.configuration import Configuration
from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


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


async def test_generate_document_number_seeds_default_scheme_when_missing(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.numbering import generate_document_number

    async with session_maker() as session:
        number = await generate_document_number(session, organisation_id=organisation_id)
        await session.commit()

    assert number == "DOC-0001"


async def test_generate_document_number_increments_the_persisted_sequence(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.numbering import generate_document_number

    async with session_maker() as session:
        first = await generate_document_number(session, organisation_id=organisation_id)
        await session.commit()

    async with session_maker() as session:
        second = await generate_document_number(session, organisation_id=organisation_id)
        await session.commit()

    assert first == "DOC-0001"
    assert second == "DOC-0002"


async def test_generate_document_number_respects_custom_scheme(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.numbering import NUMBERING_SCHEME_KEY, generate_document_number

    async with session_maker() as session:
        session.add(
            Configuration(
                organisation_id=organisation_id,
                key=NUMBERING_SCHEME_KEY,
                value={"prefix": "SOP", "separator": "/", "padding": 3, "next_sequence": 7},
            )
        )
        await session.commit()

    async with session_maker() as session:
        number = await generate_document_number(session, organisation_id=organisation_id)
        await session.commit()

    assert number == "SOP/007"

    async with session_maker() as session:
        row = (
            await session.execute(
                select(Configuration).where(
                    Configuration.organisation_id == organisation_id,
                    Configuration.key == NUMBERING_SCHEME_KEY,
                )
            )
        ).scalar_one()
        assert row.value["next_sequence"] == 8
