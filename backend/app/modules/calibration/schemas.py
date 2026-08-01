"""Pydantic schemas for the Calibration and Asset Management module, per
docs/modules/CalibrationAndAssetManagement.md and docs/API.md."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.calibration.models import AssetStatus, AssetType


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
