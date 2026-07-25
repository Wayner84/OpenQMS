"""Unit tests for the User ORM model (SQLite, ORM-level only).

Proves the (organisation_id, email) uniqueness constraint and default field values
from the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md). PostgreSQL-only
behaviour (the native ENUM type) is exercised in tests/integration, not here.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    from app.models.organisation import Organisation

    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


async def test_user_defaults_to_member_role_active_and_zero_token_version(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
) -> None:
    """A newly created user defaults to role=member, is_active=True, token_version=0."""
    from app.models.user import User, UserRole

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="new.user@example.com",
            hashed_password="not-a-real-hash",
            full_name="New User",
        )
        session.add(user)
        await session.commit()

        assert isinstance(user.id, uuid.UUID)
        assert user.role == UserRole.MEMBER
        assert user.is_active is True
        assert user.token_version == 0


async def test_user_enforces_unique_email_per_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
) -> None:
    """(organisation_id, email) must be unique."""
    from app.models.user import User

    async with session_maker() as session:
        session.add(
            User(
                organisation_id=organisation_id,
                email="duplicate@example.com",
                hashed_password="hash-a",
                full_name="First",
            )
        )
        await session.commit()

        session.add(
            User(
                organisation_id=organisation_id,
                email="duplicate@example.com",
                hashed_password="hash-b",
                full_name="Second",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
