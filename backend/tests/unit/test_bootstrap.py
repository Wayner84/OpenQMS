"""Unit tests for app/core/bootstrap.py: the no-committed-secret bootstrap admin.

Per the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#authentication):
idempotent (no-op once any user exists), skips with a warning if no admin email is
configured, and generates+logs a random password exactly once when no password is
configured.
"""

import logging
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation
from app.models.user import User, UserRole

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
async def organisation_id(session_maker: SessionMaker):  # type: ignore[no-untyped-def]
    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


async def test_creates_admin_with_configured_password(
    session_maker: SessionMaker, organisation_id: object
) -> None:
    from app.core.bootstrap import ensure_bootstrap_admin
    from app.core.security import verify_password

    async with session_maker() as session:
        await ensure_bootstrap_admin(
            session, admin_email="admin@example.com", admin_password="a-configured-password"
        )

    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        admin = result.scalar_one()

    assert admin.role == UserRole.ADMIN
    assert admin.organisation_id == organisation_id
    assert verify_password("a-configured-password", admin.hashed_password)


async def test_generates_and_logs_a_password_when_none_configured(
    session_maker: SessionMaker,
    organisation_id: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import re

    from app.core.bootstrap import ensure_bootstrap_admin
    from app.core.security import verify_password

    with caplog.at_level(logging.WARNING):
        async with session_maker() as session:
            await ensure_bootstrap_admin(
                session, admin_email="admin@example.com", admin_password=None
            )

    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        admin = result.scalar_one()

    match = re.search(r"generated password: (\S+)", caplog.text)
    assert match is not None, caplog.text
    generated_password = match.group(1)
    assert verify_password(generated_password, admin.hashed_password)


async def test_skips_with_warning_when_no_admin_email_configured(
    session_maker: SessionMaker,
    organisation_id: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.core.bootstrap import ensure_bootstrap_admin

    with caplog.at_level(logging.WARNING):
        async with session_maker() as session:
            await ensure_bootstrap_admin(session, admin_email=None, admin_password=None)

    async with session_maker() as session:
        result = await session.execute(select(func.count()).select_from(User))
        assert result.scalar_one() == 0

    assert "BOOTSTRAP_ADMIN_EMAIL" in caplog.text


async def test_is_a_no_op_once_any_user_exists(
    session_maker: SessionMaker, organisation_id: object
) -> None:
    from app.core.bootstrap import ensure_bootstrap_admin

    async with session_maker() as session:
        session.add(
            User(
                organisation_id=organisation_id,
                email="existing@example.com",
                hashed_password="irrelevant",
                full_name="Existing User",
                role=UserRole.MEMBER,
            )
        )
        await session.commit()

    async with session_maker() as session:
        await ensure_bootstrap_admin(
            session, admin_email="admin@example.com", admin_password="whatever"
        )

    async with session_maker() as session:
        result = await session.execute(select(func.count()).select_from(User))
        assert result.scalar_one() == 1
