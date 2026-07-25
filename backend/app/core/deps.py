"""Depends()-based current-user resolution, per docs/Architecture.md#layered-backend-architecture
and the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#authentication).

Every request that reaches an authenticated route resolves exactly one organisation
(from the validated token, never from client input) via `get_current_user`. Modules
that need admin-only routes depend on `get_current_admin` instead.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import TokenError, decode_access_token
from app.models.user import User, UserRole

__all__ = [
    "CurrentAdmin",
    "CurrentUser",
    "get_current_admin",
    "get_current_user",
]

_bearer_scheme = HTTPBearer(auto_error=False)

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CredentialsDependency = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


def _jwt_secret_key(settings: Annotated[Settings, Depends(get_settings)]) -> str:
    return settings.jwt_secret_key


async def get_current_user(
    credentials: CredentialsDependency,
    session: SessionDependency,
    secret_key: Annotated[str, Depends(_jwt_secret_key)],
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer` header.

    Raises `401` for a missing, invalid, expired, or revoked (logged-out) token, or
    for an inactive/deleted user — deliberately the same error for every case, so a
    caller can never distinguish "no such user" from "wrong token" from "revoked".
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials, secret_key=secret_key)
    except TokenError as exc:
        raise unauthorized from exc

    result = await session.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or user.token_version != payload.ver
        or user.organisation_id != payload.org
    ):
        raise unauthorized

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUser) -> User:
    """Require the current user to hold the admin role. Raises `403` otherwise."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return current_user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
