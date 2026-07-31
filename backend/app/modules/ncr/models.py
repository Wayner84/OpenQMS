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

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# JSONB on PostgreSQL (production/Docker); plain JSON on SQLite (fast unit tests
# only), matching app/models/configuration.py's established pattern -- see
# docs/Database.md#engines.
_JsonValue = JSONB().with_variant(JSON(), "sqlite")


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


class NcrActionStatus(str, enum.Enum):
    """Whether a corrective/preventive action for an NCR is still outstanding.
    An NCR cannot close (design decision 4) while any of its actions are `open`."""

    OPEN = "open"
    COMPLETE = "complete"


class NcrAction(Base):
    """A containment/corrective/preventive action tracked against an NCR.
    `owner_id` is an organisational assignment (who is responsible for fixing it)
    that can validly name someone without a login, matching `ncrs.raised_by_id`'s
    precedent -- see the plan's design decision 1."""

    __tablename__ = "ncr_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ncr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncrs.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[NcrActionStatus] = mapped_column(
        _ncr_enum_column(NcrActionStatus, "ncr_action_status"),
        nullable=False,
        default=NcrActionStatus.OPEN,
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NcrInvestigationToolType(str, enum.Enum):
    """The fixed set of structured investigation aids, per design decision 7 --
    optional aids attached during the Investigate/Corrective Action stages, not
    mandatory gates."""

    FIVE_WHY = "five_why"
    FISHBONE = "fishbone"
    EIGHT_D = "eight_d"
    TEN_D = "ten_d"


class NcrInvestigationTool(Base):
    """One evolving worksheet per `(ncr_id, tool_type)`, upserted via `PUT` rather
    than a separate create/update distinction -- see the plan's design decision 7.
    `data`'s shape is intentionally not modelled further at the database layer:
    each tool's structure differs enough that a flexible JSONB column is
    preferable to one table per tool type, matching `configuration.value`'s
    established precedent for flexible structured data."""

    __tablename__ = "ncr_investigation_tools"
    __table_args__ = (
        UniqueConstraint("ncr_id", "tool_type", name="uq_ncr_investigation_tools_ncr_tool_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ncr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncrs.id", ondelete="CASCADE"), nullable=False
    )
    tool_type: Mapped[NcrInvestigationToolType] = mapped_column(
        _ncr_enum_column(NcrInvestigationToolType, "ncr_investigation_tool_type"), nullable=False
    )
    data: Mapped[dict[str, object]] = mapped_column(_JsonValue, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NcrAttachment(Base):
    """A Document Management record attached as supporting evidence for an NCR.
    `document_id` is validated against the Document Management module's own
    service layer -- never its model directly, per the module-isolation rule."""

    __tablename__ = "ncr_attachments"
    __table_args__ = (
        UniqueConstraint("ncr_id", "document_id", name="uq_ncr_attachments_ncr_document"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ncr_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ncrs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
