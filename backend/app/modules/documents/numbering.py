"""Configuration-driven document numbering, per docs/Database.md#configuration-table
and the Milestone 2 plan's "Configurable numbering" section
(.hermes/plans/2026-07-26-milestone-2-document-management.md). Never hard-codes a
prefix/padding in application code -- reads (and, on first use, seeds) an
organisation-scoped `configuration` row.
"""

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration

NUMBERING_SCHEME_KEY = "document_numbering_scheme"

DEFAULT_NUMBERING_SCHEME: dict[str, Any] = {
    "prefix": "DOC",
    "separator": "-",
    "padding": 4,
    "next_sequence": 1,
}


async def generate_document_number(session: AsyncSession, *, organisation_id: uuid.UUID) -> str:
    """Generate the next document number for `organisation_id`, incrementing the
    persisted sequence in the same unit of work as the caller's own commit.

    Locks the configuration row with `SELECT ... FOR UPDATE` (a no-op on SQLite,
    which has no row-level locking and is single-writer for the unit tests that use
    it) so concurrent document creation under real PostgreSQL cannot allocate the
    same number twice. Falls back to a conservative built-in default -- and creates
    the row -- if it is ever missing; it should always exist after the seeding data
    migration, but a fresh/edge-case organisation must never fail to number a
    document.
    """
    statement = select(Configuration).where(
        Configuration.organisation_id == organisation_id,
        Configuration.key == NUMBERING_SCHEME_KEY,
    )
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        statement = statement.with_for_update()

    config_row = (await session.execute(statement)).scalar_one_or_none()

    if config_row is None:
        config_row = Configuration(
            organisation_id=organisation_id,
            key=NUMBERING_SCHEME_KEY,
            value=dict(DEFAULT_NUMBERING_SCHEME),
        )
        session.add(config_row)
        await session.flush()

    scheme = config_row.value
    prefix = scheme.get("prefix", DEFAULT_NUMBERING_SCHEME["prefix"])
    separator = scheme.get("separator", DEFAULT_NUMBERING_SCHEME["separator"])
    padding = int(cast(int, scheme.get("padding", DEFAULT_NUMBERING_SCHEME["padding"])))
    next_sequence = int(
        cast(int, scheme.get("next_sequence", DEFAULT_NUMBERING_SCHEME["next_sequence"]))
    )

    number = f"{prefix}{separator}{next_sequence:0{padding}d}"
    config_row.value = {**scheme, "next_sequence": next_sequence + 1}

    return number
