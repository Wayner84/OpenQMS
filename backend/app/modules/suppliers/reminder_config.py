"""Configuration-driven certification-expiry reminder window, per
docs/Database.md#configuration-table and the Milestone 3 plan's design decision 5
(.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md): the "expiring
soon" window is an operator-configurable number of days, never a hard-coded
literal. Read-only, like the upload-policy config it mirrors -- no sequence to
mutate, so a missing row simply falls back to the conservative built-in default
rather than being seeded on read.
"""

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration

REMINDER_WINDOW_KEY = "supplier_certification_reminder_window_days"

DEFAULT_REMINDER_WINDOW_DAYS = 30


async def get_reminder_window_days(session: AsyncSession, *, organisation_id: uuid.UUID) -> int:
    """Return the effective certification-expiry reminder window, in days, for
    `organisation_id`, falling back to the built-in default if the `configuration`
    row is missing."""
    config_row = (
        await session.execute(
            select(Configuration).where(
                Configuration.organisation_id == organisation_id,
                Configuration.key == REMINDER_WINDOW_KEY,
            )
        )
    ).scalar_one_or_none()

    if config_row is None:
        return DEFAULT_REMINDER_WINDOW_DAYS

    return int(cast(int, config_row.value.get("days", DEFAULT_REMINDER_WINDOW_DAYS)))
