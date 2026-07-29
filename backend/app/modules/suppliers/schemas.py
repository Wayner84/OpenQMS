"""Pydantic schemas for the Suppliers module, per docs/modules/Suppliers.md and
docs/API.md."""

import datetime
import decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.modules.suppliers.models import ApprovalStatus, RiskRating


class SupplierWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/suppliers (create and full update)."""

    company_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    risk_rating: RiskRating | None = None
    is_preferred: bool = False
    notes: str | None = None


class SupplierRead(BaseModel):
    """A supplier's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    company_id: uuid.UUID
    approval_status: ApprovalStatus
    risk_rating: RiskRating | None
    is_preferred: bool
    notes: str | None
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None


class SupplierListResponse(BaseModel):
    """GET /api/v1/suppliers response body, per docs/API.md#pagination."""

    items: list[SupplierRead]
    total: int
    limit: int
    offset: int


class SupplierCertificationWriteRequest(BaseModel):
    """Shared shape for POST and PATCH .../certifications."""

    certification_type: str
    certificate_document_id: uuid.UUID | None = None
    issued_date: datetime.date | None = None
    expiry_date: datetime.date | None = None


class SupplierCertificationRead(BaseModel):
    """A certification's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    certification_type: str
    certificate_document_id: uuid.UUID | None
    issued_date: datetime.date | None
    expiry_date: datetime.date | None


class SupplierCertificationListResponse(BaseModel):
    """GET .../certifications (and .../certifications/expiring) response body."""

    items: list[SupplierCertificationRead]
    total: int
    limit: int
    offset: int


class SupplierPerformanceRecordWriteRequest(BaseModel):
    """POST .../performance request body."""

    period: str
    score: decimal.Decimal = Field(max_digits=10, decimal_places=2)
    notes: str | None = None


class SupplierPerformanceRecordRead(BaseModel):
    """A performance record's public shape."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    period: str
    score: decimal.Decimal
    notes: str | None
    created_by_id: uuid.UUID | None


class SupplierPerformanceRecordListResponse(BaseModel):
    """GET .../performance response body."""

    items: list[SupplierPerformanceRecordRead]
    total: int
    limit: int
    offset: int
