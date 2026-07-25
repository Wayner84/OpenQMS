"""Unit tests for the organisations/configuration ORM models (SQLite, ORM-level only).

Proves the multi-tenancy baseline (docs/Database.md#multi-tenancy-baseline) and the
(organisation_id, key) uniqueness constraint on configuration rows. JSONB-specific
behaviour is out of scope here — see tests/integration for the real PostgreSQL path.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def session_maker():  # type: ignore[no-untyped-def]
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_organisation_round_trips_with_uuid_pk(session_maker) -> None:  # type: ignore[no-untyped-def]
    """An Organisation can be inserted and read back with a generated UUID id."""
    from app.models.organisation import Organisation

    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()

        assert isinstance(org.id, uuid.UUID)
        assert org.created_at is not None


async def test_configuration_enforces_unique_key_per_organisation(session_maker) -> None:  # type: ignore[no-untyped-def]
    """(organisation_id, key) must be unique, per docs/Database.md#configuration-table."""
    from app.models.configuration import Configuration
    from app.models.organisation import Organisation

    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.flush()

        session.add(
            Configuration(organisation_id=org.id, key="instance.display_name", value={"v": "A"})
        )
        await session.commit()

        session.add(
            Configuration(organisation_id=org.id, key="instance.display_name", value={"v": "B"})
        )
        with pytest.raises(IntegrityError):
            await session.commit()
