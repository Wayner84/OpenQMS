"""SQLAlchemy models for the NCR module: non-conformance reports and their status
history. Per docs/modules/NCR.md and the Milestone 4 plan
(.hermes/plans/2026-07-29-milestone-4-ncr.md).

`raised_by_id` references `people.id` (an organisational assignment -- who
identified the issue -- that can validly name someone without a login, matching
`documents.owner_id`'s precedent); `ncr_status_history.changed_by_id` references
`users.id` (a workflow transition is an action performed by an authenticated API
caller, matching `document_approvals`/`document_acknowledgements`'s precedent). See
the plan's design decision 1 for the full reasoning.
"""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NcrType(str, enum.Enum):
    """Internal vs supplier non-conformance, per docs/Database.md#naming-conventions."""

    INTERNAL = "internal"
    SUPPLIER = "supplier"


class NcrStatus(str, enum.Enum):
    """The one-directional workflow sequence, in order. See the plan's design
    decision 3 -- a transition must move to exactly the next status in this
    sequence, never skip ahead or move backward."""

    OPEN = "open"
    INVESTIGATE = "investigate"
    CONTAINMENT = "containment"
    CORRECTIVE_ACTION = "corrective_action"
    VERIFICATION = "verification"
    CLOSED = "closed"


NCR_STATUS_SEQUENCE: list[NcrStatus] = [
    NcrStatus.OPEN,
    NcrStatus.INVESTIGATE,
    NcrStatus.CONTAINMENT,
    NcrStatus.CORRECTIVE_ACTION,
    NcrStatus.VERIFICATION,
    NcrStatus.CLOSED,
]


def _ncr_enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Ncr(Base):
    """A non-conformance report."""

    __tablename__ = "ncrs"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_ncrs_org_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    number: Mapped[str] = mapped_column(nullable=False)
    type: Mapped[NcrType] = mapped_column(_ncr_enum_column(NcrType, "ncr_type"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    status: Mapped[NcrStatus] = mapped_column(
        _ncr_enum_column(NcrStatus, "ncr_status"), nullable=False, default=NcrStatus.OPEN
    )
    raised_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    closed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NcrStatusHistory(Base):
    """Immutable audit trail of every workflow transition for an NCR. No update/
    delete route, matching `document_versions`/`document_approvals`'s existing
    immutable-history precedent."""

    __tablename__ = "ncr_status_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ncr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncrs.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[NcrStatus | None] = mapped_column(
        _ncr_enum_column(NcrStatus, "ncr_status"), nullable=True
    )
    to_status: Mapped[NcrStatus] = mapped_column(
        _ncr_enum_column(NcrStatus, "ncr_status"), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
