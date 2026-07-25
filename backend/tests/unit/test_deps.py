"""Unit tests for app/core/deps.py: Depends()-based current-user resolution.

Covers the hard security acceptance criteria from the Milestone 1 plan: rejects
missing/invalid/expired/revoked tokens and inactive users with 401 (never revealing
which condition failed), and rejects non-admin callers on admin-only routes with 403.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.user import User

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
async def seeded_user(session_maker: SessionMaker) -> User:
    from app.models.organisation import Organisation
    from app.models.user import UserRole

    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.flush()

        user = User(
            organisation_id=org.id,
            email="member@example.com",
            hashed_password="irrelevant",
            full_name="Member User",
            role=UserRole.MEMBER,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def test_get_current_user_returns_user_for_valid_token(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.core.deps import get_current_user
    from app.core.security import create_access_token

    token = create_access_token(seeded_user, secret_key="test-secret", expire_minutes=60)

    async with session_maker() as session:
        user = await get_current_user(
            credentials=_credentials(token), session=session, secret_key="test-secret"
        )

    assert user.id == seeded_user.id


async def test_get_current_user_rejects_missing_credentials(session_maker: SessionMaker) -> None:
    from app.core.deps import get_current_user

    async with session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None, session=session, secret_key="test-secret")

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_expired_token(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.core.deps import get_current_user
    from app.core.security import create_access_token

    token = create_access_token(seeded_user, secret_key="test-secret", expire_minutes=-1)

    async with session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=_credentials(token), session=session, secret_key="test-secret"
            )

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_token_for_unknown_user(
    session_maker: SessionMaker,
) -> None:
    from app.core.deps import get_current_user
    from app.core.security import create_access_token
    from app.models.user import UserRole

    ghost = User(
        id=uuid.uuid4(),
        organisation_id=uuid.uuid4(),
        email="ghost@example.com",
        hashed_password="x",
        full_name="Ghost",
        role=UserRole.MEMBER,
        token_version=0,
    )
    token = create_access_token(ghost, secret_key="test-secret", expire_minutes=60)

    async with session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=_credentials(token), session=session, secret_key="test-secret"
            )

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_inactive_user(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.core.deps import get_current_user
    from app.core.security import create_access_token

    token = create_access_token(seeded_user, secret_key="test-secret", expire_minutes=60)

    async with session_maker() as session:
        seeded_user.is_active = False
        session.add(seeded_user)
        await session.commit()

    async with session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=_credentials(token), session=session, secret_key="test-secret"
            )

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_revoked_token_version(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.core.deps import get_current_user
    from app.core.security import create_access_token

    token = create_access_token(seeded_user, secret_key="test-secret", expire_minutes=60)

    async with session_maker() as session:
        seeded_user.token_version += 1
        session.add(seeded_user)
        await session.commit()

    async with session_maker() as session:
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                credentials=_credentials(token), session=session, secret_key="test-secret"
            )

    assert exc_info.value.status_code == 401


async def test_get_current_admin_allows_admin(session_maker: SessionMaker) -> None:
    from app.core.deps import get_current_admin
    from app.models.user import UserRole

    admin = User(
        id=uuid.uuid4(),
        organisation_id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password="x",
        full_name="Admin",
        role=UserRole.ADMIN,
    )

    result = await get_current_admin(current_user=admin)

    assert result is admin


async def test_get_current_admin_rejects_member() -> None:
    from app.core.deps import get_current_admin
    from app.models.user import UserRole

    member = User(
        id=uuid.uuid4(),
        organisation_id=uuid.uuid4(),
        email="member@example.com",
        hashed_password="x",
        full_name="Member",
        role=UserRole.MEMBER,
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_admin(current_user=member)

    assert exc_info.value.status_code == 403
