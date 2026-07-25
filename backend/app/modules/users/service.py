"""User management business logic: admin-only create/list/update within one organisation.

Per the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#2-user-management):
every operation is scoped to the caller's organisation (never another's), and two
safety guards prevent organisation lockout — an admin cannot deactivate or demote
themselves via this module, and the last remaining active admin in an organisation
cannot be deactivated or demoted by anyone.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole


class DuplicateEmailError(Exception):
    """Raised when creating a user whose email already exists in the organisation."""


class UserNotFoundError(Exception):
    """Raised when the target user id doesn't exist in the caller's organisation."""


class LastAdminGuardError(Exception):
    """Raised when an update would self-lock or organisation-lock out of admin access."""


async def create_user(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    email: str,
    full_name: str,
    password: str,
    role: UserRole,
) -> User:
    """Create a user in `organisation_id`. Raises `DuplicateEmailError` on email clash."""
    existing = (
        await session.execute(
            select(User).where(User.organisation_id == organisation_id, User.email == email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateEmailError(
            f"A user with email {email!r} already exists in this organisation"
        )

    user = User(
        organisation_id=organisation_id,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(
    session: AsyncSession, *, organisation_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[User], int]:
    """Return a page of users in `organisation_id`, plus the total matching count."""
    total = (
        await session.execute(
            select(func.count()).select_from(User).where(User.organisation_id == organisation_id)
        )
    ).scalar_one()

    result = await session.execute(
        select(User)
        .where(User.organisation_id == organisation_id)
        .order_by(User.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def _get_org_scoped_user(
    session: AsyncSession, *, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = (
        await session.execute(
            select(User).where(User.id == user_id, User.organisation_id == organisation_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(f"No user {user_id} in this organisation")
    return user


async def _count_other_active_admins(
    session: AsyncSession, *, organisation_id: uuid.UUID, excluding_user_id: uuid.UUID
) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.organisation_id == organisation_id,
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
                User.id != excluding_user_id,
            )
        )
    ).scalar_one()


async def update_user(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    acting_user: User,
    target_user_id: uuid.UUID,
    full_name: str | None,
    role: UserRole | None,
    is_active: bool | None,
) -> User:
    """Apply a partial update to a user in `organisation_id`.

    Raises `UserNotFoundError` for an unknown or cross-organisation id, and
    `LastAdminGuardError` if the update would deactivate/demote the acting admin
    themselves, or would leave the organisation with zero active admins.
    """
    target = await _get_org_scoped_user(
        session, organisation_id=organisation_id, user_id=target_user_id
    )

    will_deactivate = is_active is False and target.is_active
    will_demote = role is not None and role != UserRole.ADMIN and target.role == UserRole.ADMIN

    if will_deactivate or will_demote:
        if target.id == acting_user.id:
            raise LastAdminGuardError("An admin cannot deactivate or demote themselves")
        if target.role == UserRole.ADMIN:
            other_admins = await _count_other_active_admins(
                session, organisation_id=organisation_id, excluding_user_id=target.id
            )
            if other_admins == 0:
                raise LastAdminGuardError(
                    "Cannot deactivate or demote the last active admin in this organisation"
                )

    if full_name is not None:
        target.full_name = full_name
    if role is not None:
        target.role = role
    if is_active is not None:
        target.is_active = is_active

    await session.commit()
    await session.refresh(target)
    return target
