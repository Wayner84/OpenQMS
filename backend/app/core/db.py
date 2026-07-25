"""Async SQLAlchemy engine and session management.

A single `SessionFactory` wraps one engine and `async_sessionmaker`, built from
`DATABASE_URL`. Routers depend on `get_session` (via FastAPI `Depends()`) for a
session scoped to one request; services never create their own engine or session
(see docs/Database.md#connection-and-session-management).
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


class SessionFactory:
    """Owns one async engine and sessionmaker for a given database URL."""

    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, future=True)
        self._session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """FastAPI dependency yielding an AsyncSession scoped to one request."""
        async with self._session_maker() as session:
            yield session


def build_session_factory(database_url: str) -> SessionFactory:
    """Construct a SessionFactory for an arbitrary database URL (used directly in tests)."""
    return SessionFactory(database_url)


@lru_cache
def get_session_factory() -> SessionFactory:
    """Return the process-wide SessionFactory, built from Settings.database_url."""
    return build_session_factory(get_settings().database_url)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding the process-wide AsyncSession for one request."""
    async for session in get_session_factory().get_session():
        yield session
