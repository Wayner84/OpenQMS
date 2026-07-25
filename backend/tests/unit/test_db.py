"""Unit tests for async SQLAlchemy engine/session construction (SQLite, ORM-level only)."""

from sqlalchemy import text


async def test_get_session_yields_a_working_async_session() -> None:
    """The get_session dependency must yield an AsyncSession that can run a query."""
    from app.core.db import build_session_factory

    session_factory = build_session_factory("sqlite+aiosqlite:///:memory:")

    async for session in session_factory.get_session():
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
