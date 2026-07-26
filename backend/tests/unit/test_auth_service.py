"""Unit tests for app/modules/auth/service.py (SQLite, ORM-level only).

Login failure (wrong password, unknown email, inactive user) must raise the same
`InvalidCredentialsError` in every case so the router never reveals which one
occurred, per the Milestone 1 plan's security assumptions.
"""

from collections.abc import AsyncIterator

import pytest
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
    from app.core.security import hash_password
    from app.models.organisation import Organisation

    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.flush()

        user = User(
            organisation_id=org.id,
            email="active@example.com",
            hashed_password=hash_password("correct-password"),
            full_name="Active User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def test_authenticate_user_succeeds_with_correct_credentials(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.modules.auth.service import authenticate_user

    async with session_maker() as session:
        user = await authenticate_user(
            session, email="active@example.com", password="correct-password"
        )

    assert user.id == seeded_user.id


async def test_authenticate_user_rejects_wrong_password(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.modules.auth.service import InvalidCredentialsError, authenticate_user

    async with session_maker() as session:
        with pytest.raises(InvalidCredentialsError):
            await authenticate_user(session, email="active@example.com", password="wrong-password")


async def test_authenticate_user_rejects_unknown_email(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.modules.auth.service import InvalidCredentialsError, authenticate_user

    async with session_maker() as session:
        with pytest.raises(InvalidCredentialsError):
            await authenticate_user(
                session, email="nobody@example.com", password="correct-password"
            )


async def test_authenticate_user_rejects_inactive_user_even_with_correct_password(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.modules.auth.service import InvalidCredentialsError, authenticate_user

    async with session_maker() as session:
        seeded_user.is_active = False
        session.add(seeded_user)
        await session.commit()

    async with session_maker() as session:
        with pytest.raises(InvalidCredentialsError):
            await authenticate_user(
                session, email="active@example.com", password="correct-password"
            )


async def test_authenticate_user_performs_password_verification_even_for_unknown_email(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    """An unknown email must still pay Argon2id's deliberately-slow verification cost.

    Otherwise a login request for a real, active email (which always reaches
    `verify_password`) takes measurably longer than one for a nonexistent email
    (which would short-circuit before it), letting an attacker enumerate valid
    accounts by response timing even though the response body/status are identical.
    """
    from unittest.mock import patch

    from app.modules.auth.service import InvalidCredentialsError, authenticate_user

    with patch("app.modules.auth.service.verify_password", return_value=False) as mock_verify:
        async with session_maker() as session:
            with pytest.raises(InvalidCredentialsError):
                await authenticate_user(session, email="nobody@example.com", password="whatever")

    mock_verify.assert_called_once()


async def test_authenticate_user_performs_password_verification_even_for_inactive_user(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    """Same timing side-channel as above, for a deactivated account."""
    from unittest.mock import patch

    from app.modules.auth.service import InvalidCredentialsError, authenticate_user

    async with session_maker() as session:
        seeded_user.is_active = False
        session.add(seeded_user)
        await session.commit()

    with patch("app.modules.auth.service.verify_password", return_value=False) as mock_verify:
        async with session_maker() as session:
            with pytest.raises(InvalidCredentialsError):
                await authenticate_user(
                    session, email="active@example.com", password="correct-password"
                )

    mock_verify.assert_called_once()


async def test_revoke_tokens_increments_token_version(
    session_maker: SessionMaker, seeded_user: User
) -> None:
    from app.modules.auth.service import authenticate_user, revoke_tokens

    assert seeded_user.token_version == 0

    async with session_maker() as session:
        user = await authenticate_user(
            session, email="active@example.com", password="correct-password"
        )
        await revoke_tokens(session, user)
        assert user.token_version == 1

    async with session_maker() as session:
        user_again = await authenticate_user(
            session, email="active@example.com", password="correct-password"
        )
        assert user_again.token_version == 1
