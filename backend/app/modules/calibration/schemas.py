"""Pydantic schemas for the Calibration and Asset Management module, per
docs/modules/CalibrationAndAssetManagement.md and docs/API.md."""

import datetime
import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.calibration.models import (
    AssetStatus,
    AssetType,
    CalibrationIntervalUnit,
    CalibrationResult,
)


class AssetWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/calibration/assets (create and full
    update)."""

    asset_tag: str
    name: str
    asset_type: AssetType
    serial_number: str | None = None
    location: str | None = None
    owner_id: uuid.UUID | None = None
    status: AssetStatus = AssetStatus.IN_SERVICE
    purchase_date: datetime.date | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    asset_tag: str
    name: str
    asset_type: AssetType
    serial_number: str | None
    location: str | None
    owner_id: uuid.UUID | None
    status: AssetStatus
    purchase_date: datetime.date | None
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID


class AssetListResponse(BaseModel):
    items: list[AssetRead]
    total: int
    limit: int
    offset: int


class CalibrationScheduleCreateRequest(BaseModel):
    """POST /api/v1/calibration/assets/{id}/schedule request body."""

    interval_value: int = Field(gt=0)
    interval_unit: CalibrationIntervalUnit


class CalibrationScheduleUpdateRequest(BaseModel):
    """PATCH /api/v1/calibration/assets/{id}/schedule request body.

    A positive interval is required when editing; `next_due_date` may establish
    an initial baseline or override the computed date.
    """

    interval_value: int = Field(gt=0)
    interval_unit: CalibrationIntervalUnit
    next_due_date: datetime.date | None = None


class CalibrationScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    interval_value: int
    interval_unit: CalibrationIntervalUnit
    next_due_date: datetime.date | None
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID


class CalibrationEventCreateRequest(BaseModel):
    """POST /api/v1/calibration/assets/{id}/events request body.

    Enforces the module's `performed_by_id`/`performed_by_supplier_id` mutual-
    exclusivity invariant (plan design decision 3), mirroring the People module's
    `is_employee`/`company_id` invariant: both may be omitted (a historical event
    whose performer wasn't recorded), but setting both is rejected -- a single
    calibration event was performed either in-house or by one external calibration
    house, never attributed to both at once.
    """

    performed_at: datetime.date
    performed_by_id: uuid.UUID | None = None
    performed_by_supplier_id: uuid.UUID | None = None
    certificate_document_id: uuid.UUID | None = None
    result: CalibrationResult
    notes: str | None = None

    @model_validator(mode="after")
    def _check_performer_invariant(self) -> Self:
        if self.performed_by_id is not None and self.performed_by_supplier_id is not None:
            raise ValueError(
                "A calibration event cannot have both performed_by_id and "
                "performed_by_supplier_id set"
            )
        return self


class CalibrationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    performed_at: datetime.date
    performed_by_id: uuid.UUID | None
    performed_by_supplier_id: uuid.UUID | None
    certificate_document_id: uuid.UUID | None
    result: CalibrationResult
    next_due_date: datetime.date | None
    notes: str | None
    created_by_id: uuid.UUID


class CalibrationEventListResponse(BaseModel):
    items: list[CalibrationEventRead]
    total: int
    limit: int
    offset: int
