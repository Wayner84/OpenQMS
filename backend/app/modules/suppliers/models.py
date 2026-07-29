"""SQLAlchemy models for the Suppliers module: approved-supplier records,
certifications, and performance history. Per docs/modules/Suppliers.md and the
Milestone 3 plan (.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).

A `Supplier` wraps a People `Company` row (name/address/contacts already live
there -- see docs/modules/People.md) with supplier-specific fields. `risk_rating`
and `SupplierPerformanceRecord.score` are plain operator-entered values, not an
auto-computed score -- the configurable risk-scoring engine shared with NCR and
Risk Assessments is an explicit open research question (docs/TODO.md Task 37),
deliberately not resolved by this module (see the Milestone 3 plan's design
decision 3).
"""

import datetime
import decimal
import enum
import uuid

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApprovalStatus(str, enum.Enum):
    """Fixed set of supplier approval states, per docs/Database.md#naming-conventions."""

    APPROVED = "approved"
    PENDING = "pending"
    SUSPENDED = "suspended"


class RiskRating(str, enum.Enum):
    """A plain, operator-set risk rating -- not an auto-computed score. See this
    module's docstring."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Supplier(Base):
    """An approved-supplier record wrapping a People `Company` row."""

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(
            ApprovalStatus,
            name="supplier_approval_status",
            native_enum=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    risk_rating: Mapped[RiskRating | None] = mapped_column(
        Enum(
            RiskRating,
            name="supplier_risk_rating",
            native_enum=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SupplierCertification(Base):
    """A certification/accreditation held by a supplier (e.g. ISO 9001, AS9100).

    `certification_type` is free text, not an enum -- the set of accreditation types
    an operator wants to track is inherently open-ended (see docs/modules/Suppliers.md).
    """

    __tablename__ = "supplier_certifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    certification_type: Mapped[str] = mapped_column(String, nullable=False)
    certificate_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    issued_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SupplierPerformanceRecord(Base):
    """A point-in-time performance entry for a supplier. Append-only from the API's
    perspective (no update/delete route) -- a performance record is a historical
    entry, not a mutable field, matching document_versions/document_approvals'
    existing immutable-history pattern."""

    __tablename__ = "supplier_performance_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[decimal.Decimal] = mapped_column(Numeric, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
