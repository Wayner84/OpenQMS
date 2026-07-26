"""Authentication business logic: login and logout/revocation.

Per the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#authentication):
login is looked up by email only, not by (organisation_id, email) — Milestone 1 has
exactly one organisation in practice (no UI exists to create another), so the token's
organisation claim is resolved from the matched user row rather than supplied by the
client. Multi-organisation login is deferred (see docs/FutureIdeas.md).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


class InvalidCredentialsError(Exception):
    """Raised for any login failure: wrong password, unknown email, or inactive user.

    Deliberately one exception/message for all three cases so the API response never
    reveals which one occurred.
    """


# Argon2id verification is deliberately slow. Used in place of a real hash when no
# user matches the supplied email, so an unknown-email login pays the same
# verification cost as a wrong-password one — otherwise the two are distinguishable
# by response timing alone, even though their response body/status are identical.
_DUMMY_HASH = hash_password("no-such-user-dummy-password-for-constant-time-comparison")


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    """Return the active user matching `email`/`password`, or raise `InvalidCredentialsError`."""
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    hashed_password = user.hashed_password if user is not None else _DUMMY_HASH
    password_matches = verify_password(password, hashed_password)
    if user is None or not user.is_active or not password_matches:
        raise InvalidCredentialsError("Incorrect email or password")
    return user


async def revoke_tokens(session: AsyncSession, user: User) -> None:
    """Increment `user.token_version`, invalidating every access token issued so far."""
    user.token_version += 1
    await session.commit()
