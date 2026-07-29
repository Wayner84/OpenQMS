"""Configuration-driven NCR numbering, per docs/Database.md#configuration-table and
the Milestone 4 plan's design decision 6
(.hermes/plans/2026-07-29-milestone-4-ncr.md). One `ncr_numbering_scheme`
configuration row holds independent prefix/sequence state for `internal` and
`supplier` NCRs -- never a hard-coded prefix in application code.
"""

import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration
from app.modules.ncr.models import NcrType

NUMBERING_SCHEME_KEY = "ncr_numbering_scheme"

DEFAULT_NUMBERING_SCHEME: dict[str, dict[str, Any]] = {
    "internal": {"prefix": "NCR", "separator": "-", "padding": 4, "next_sequence": 1},
    "supplier": {"prefix": "SNCR", "separator": "-", "padding": 4, "next_sequence": 1},
}


async def generate_ncr_number(
    session: AsyncSession, *, organisation_id: uuid.UUID, type: NcrType
) -> str:
    """Generate the next NCR number for `organisation_id` and `type`, incrementing
    that type's persisted sequence in the same unit of work as the caller's own
    commit.

    Locks the configuration row with `SELECT ... FOR UPDATE` (a no-op on SQLite,
    which has no row-level locking and is single-writer for the unit tests that use
    it) so concurrent NCR creation under real PostgreSQL cannot allocate the same
    number twice -- mirrors `documents.numbering.generate_document_number`. Falls
    back to a conservative built-in default -- and creates the row -- if it is ever
    missing; it should always exist after the seeding data migration, but a fresh/
    edge-case organisation must never fail to number an NCR.
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
            value={key: dict(value) for key, value in DEFAULT_NUMBERING_SCHEME.items()},
        )
        session.add(config_row)
        await session.flush()

    scheme = config_row.value
    type_key = type.value
    type_scheme = cast("dict[str, Any]", scheme.get(type_key, DEFAULT_NUMBERING_SCHEME[type_key]))

    prefix = type_scheme.get("prefix", DEFAULT_NUMBERING_SCHEME[type_key]["prefix"])
    separator = type_scheme.get("separator", DEFAULT_NUMBERING_SCHEME[type_key]["separator"])
    padding = int(
        cast(int, type_scheme.get("padding", DEFAULT_NUMBERING_SCHEME[type_key]["padding"]))
    )
    next_sequence = int(
        cast(
            int,
            type_scheme.get("next_sequence", DEFAULT_NUMBERING_SCHEME[type_key]["next_sequence"]),
        )
    )

    number = f"{prefix}{separator}{next_sequence:0{padding}d}"
    updated_scheme: dict[str, object] = dict(scheme)
    updated_scheme[type_key] = {**type_scheme, "next_sequence": next_sequence + 1}
    config_row.value = updated_scheme

    return number
