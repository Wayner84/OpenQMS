"""Response contract for the calibration and maintenance due list."""

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel


class DueItem(BaseModel):
    asset_id: uuid.UUID
    asset_tag: str
    asset_name: str
    due_type: Literal["calibration", "maintenance"]
    next_due_date: datetime.date


class DueListResponse(BaseModel):
    items: list[DueItem]
    total: int
    limit: int
    offset: int
    within_days: int
