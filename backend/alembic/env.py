"""Alembic environment: targets the app's declarative Base and DATABASE_URL.

Runs migrations through the same async engine machinery as the application (see
docs/Database.md#orm-and-migrations), using SQLAlchemy's recommended
run_sync pattern so synchronous Alembic operations work against the async driver.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context
from app.core.config import get_settings
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve the database URL from the application's Settings, not alembic.ini."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection, emitting SQL to stdout."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations against an already-open synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database using the async engine."""
    connectable: AsyncEngine = create_async_engine(get_database_url(), future=True)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
