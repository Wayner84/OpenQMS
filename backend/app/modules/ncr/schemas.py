"""Pydantic schemas for the NCR module, per docs/modules/NCR.md and docs/API.md."""

import datetime
import uuid
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.ncr.models import NcrStatus, NcrType


class NcrCreateRequest(BaseModel):
    """POST /api/v1/ncr request body."""

    type: NcrType
    product_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    raised_by_id: uuid.UUID
    description: str
    root_cause_summary: str | None = None

    @model_validator(mode="after")
    def _check_supplier_invariant(self) -> Self:
        if self.type == NcrType.SUPPLIER and self.supplier_id is None:
            raise ValueError("A supplier NCR (type=supplier) must have a supplier_id")
        if self.type == NcrType.INTERNAL and self.supplier_id is not None:
            raise ValueError("An internal NCR (type=internal) cannot have a supplier_id")
        return self


class NcrUpdateRequest(BaseModel):
    """PATCH /api/v1/ncr/{id} request body. `status` is deliberately absent -- it
    only changes via POST /api/v1/ncr/{id}/transition."""

    product_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    raised_by_id: uuid.UUID
    description: str
    root_cause_summary: str | None = None
    type: NcrType

    @model_validator(mode="after")
    def _check_supplier_invariant(self) -> Self:
        if self.type == NcrType.SUPPLIER and self.supplier_id is None:
            raise ValueError("A supplier NCR (type=supplier) must have a supplier_id")
        if self.type == NcrType.INTERNAL and self.supplier_id is not None:
            raise ValueError("An internal NCR (type=internal) cannot have a supplier_id")
        return self


class NcrRead(BaseModel):
    """An NCR's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    number: str
    type: NcrType
    product_id: uuid.UUID | None
    supplier_id: uuid.UUID | None
    status: NcrStatus
    raised_by_id: uuid.UUID
    description: str
    root_cause_summary: str | None
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID
    closed_at: datetime.datetime | None


class NcrListResponse(BaseModel):
    """GET /api/v1/ncr response body, per docs/API.md#pagination."""

    items: list[NcrRead]
    total: int
    limit: int
    offset: int


class NcrTransitionRequest(BaseModel):
    """POST /api/v1/ncr/{id}/transition request body."""

    to_status: NcrStatus
    comments: str | None = None


class NcrStatusHistoryRead(BaseModel):
    """A status-history entry's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ncr_id: uuid.UUID
    from_status: NcrStatus | None
    to_status: NcrStatus
    changed_by_id: uuid.UUID
    changed_at: datetime.datetime
    comments: str | None


class NcrStatusHistoryListResponse(BaseModel):
    """GET /api/v1/ncr/{id}/status-history response body."""

    items: list[NcrStatusHistoryRead]
    total: int
    limit: int
    offset: int
