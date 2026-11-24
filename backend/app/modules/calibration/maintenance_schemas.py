"""Request/response schema for asset maintenance schedules."""

import datetime
import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.calibration.models import CalibrationIntervalUnit


class MaintenanceScheduleWrite(BaseModel):
    interval_value: int = Field(gt=0)
    interval_unit: CalibrationIntervalUnit
    next_due_date: datetime.date | None = None


class MaintenanceScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    asset_id: uuid.UUID
    interval_value: int | None = None
    interval_unit: CalibrationIntervalUnit | None = None
    next_due_date: datetime.date | None = None
    created_by_id: uuid.UUID | None = None
    updated_by_id: uuid.UUID | None = None


class MaintenanceScheduleEmpty(BaseModel):
    asset_id: uuid.UUID
    id: None = None
    interval_value: None = None
    interval_unit: None = None
    next_due_date: None = None
    created_by_id: None = None
    updated_by_id: None = None


class MaintenanceScheduleUpdateRequest(BaseModel):
    interval_value: int | None = Field(default=None, gt=0)
    interval_unit: CalibrationIntervalUnit | None = None
    next_due_date: datetime.date | None = None

    @model_validator(mode="after")
    def reject_null_interval(self) -> Self:
        for field in ("interval_value", "interval_unit"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
