"""Bootstrap admin mechanism: creates the first admin account with no committed secret.

Per the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#authentication):
run once, after migrations, before the backend starts serving traffic (see
docker-entrypoint.sh). Idempotent: a no-op once any user exists in any organisation,
so restarts never create a second admin. `BOOTSTRAP_ADMIN_EMAIL` must be set for
bootstrap to do anything; `BOOTSTRAP_ADMIN_PASSWORD` is optional — if unset, a random
password is generated and logged once (never written anywhere else), so no default
or committed credential ever exists.
"""

import asyncio
import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.organisation import Organisation
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

__all__ = ["ensure_bootstrap_admin", "main"]


async def ensure_bootstrap_admin(
    session: AsyncSession, *, admin_email: str | None, admin_password: str | None
) -> None:
    """Create exactly one admin user for the default organisation, if none exists yet."""
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count > 0:
        return

    if not admin_email:
        logger.warning(
            "Bootstrap admin skipped: BOOTSTRAP_ADMIN_EMAIL is not set and no users exist yet. "
            "Set BOOTSTRAP_ADMIN_EMAIL (and optionally BOOTSTRAP_ADMIN_PASSWORD) and restart "
            "the backend to create the first admin account."
        )
        return

    organisation = (
        await session.execute(select(Organisation).where(Organisation.slug == "default"))
    ).scalar_one_or_none()
    if organisation is None:
        logger.warning("Bootstrap admin skipped: no default organisation found.")
        return

    password = admin_password or secrets.token_urlsafe(18)
    session.add(
        User(
            organisation_id=organisation.id,
            email=admin_email,
            hashed_password=hash_password(password),
            full_name="Administrator",
            role=UserRole.ADMIN,
        )
    )
    await session.commit()

    if admin_password:
        logger.warning("Bootstrap admin account created for %s.", admin_email)
    else:
        logger.warning(
            "Bootstrap admin account created for %s with a generated password: %s "
            "-- log in and change it immediately; this password is never shown again.",
            admin_email,
            password,
        )


async def main() -> None:
    """CLI entry point: `python -m app.core.bootstrap`, run from docker-entrypoint.sh."""
    from app.core.config import get_settings
    from app.core.db import get_session_factory

    settings = get_settings()
    session_factory = get_session_factory()
    async for session in session_factory.get_session():
        await ensure_bootstrap_admin(
            session,
            admin_email=settings.bootstrap_admin_email,
            admin_password=settings.bootstrap_admin_password,
        )
    await session_factory.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
