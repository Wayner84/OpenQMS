"""Organisation-configured calibration/maintenance reminder window."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration

REMINDER_WINDOW_KEY = "calibration_due_reminder_window_days"
DEFAULT_REMINDER_WINDOW_DAYS = 30
MAX_REMINDER_WINDOW_DAYS = 3650


async def get_reminder_window_days(session: AsyncSession, *, organisation_id: uuid.UUID) -> int:
    row = (
        await session.execute(
            select(Configuration).where(
                Configuration.organisation_id == organisation_id,
                Configuration.key == REMINDER_WINDOW_KEY,
            )
        )
    ).scalar_one_or_none()
    value = DEFAULT_REMINDER_WINDOW_DAYS if row is None else row.value.get("days")
    if type(value) is not int or not 0 <= value <= MAX_REMINDER_WINDOW_DAYS:
        return DEFAULT_REMINDER_WINDOW_DAYS
    return value
