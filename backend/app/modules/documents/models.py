"""SQLAlchemy models for the Document Management module: categories, tags,
documents, and their immutable versions. Per docs/modules/DocumentManagement.md and
the Milestone 2 plan
(.hermes/plans/2026-07-26-milestone-2-document-management.md#1-schema).

`Document.current_version_id` and `DocumentVersion.document_id` form a circular
reference (a document points at its current version; a version points back at its
document), resolved with `use_alter=True` on the `documents` side so both tables can
still be created with a normal `CREATE TABLE`/`ALTER TABLE ... ADD CONSTRAINT` pair
(see the Alembic migration for the explicit two-step DDL).

`document_approvals` and `document_acknowledgements` (added in later Milestone 2
slices) attribute their actor to `users.id`, not `people.id` -- see the "Design
decisions" section of the Milestone 2 plan for why.
"""

import datetime
import enum
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentStatus(str, enum.Enum):
    """A document's overall, service-maintained state -- see the Milestone 2 plan's
    "Workflow (state machine)" section for how this is derived from version state."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    OBSOLETE = "obsolete"


class DocumentVersionStatus(str, enum.Enum):
    """A single version's place in the approval workflow. `REJECTED` is terminal for
    that version -- QMS revision history is never overwritten or silently reset; a
    new version must be created to try again."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    OBSOLETE = "obsolete"


class ApprovalDecision(str, enum.Enum):
    """A single recorded approval decision for a version."""

    APPROVED = "approved"
    REJECTED = "rejected"


def _native_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class DocumentCategory(Base):
    """A node in an organisation's document category tree."""

    __tablename__ = "document_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_categories.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentTag(Base):
    """A free-form, organisation-scoped label a document can be linked to."""

    __tablename__ = "document_tags"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name", name="uq_document_tags_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentTagLink(Base):
    """Many-to-many join between `documents` and `document_tags`."""

    __tablename__ = "document_tag_links"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_tags.id"), primary_key=True)


class Document(Base):
    """A controlled document. `number` is server-generated (never client-supplied)
    from the organisation's configurable numbering scheme -- see
    `app/modules/documents/numbering.py`. `status` mirrors the current/latest
    version's workflow stage; `deleted_at` implements soft delete per
    docs/Database.md#soft-delete-and-audit-trail."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_documents_org_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_categories.id"), nullable=True
    )
    number: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        _native_enum(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.DRAFT,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", use_alter=True, name="fk_documents_current_version_id"),
        nullable=True,
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentVersion(Base):
    """One immutable revision of a document's file. Never mutated after creation
    except for `status` (via the workflow endpoints, which log their own
    `document_approvals` trail)."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_doc_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DocumentVersionStatus] = mapped_column(
        _native_enum(DocumentVersionStatus, "document_version_status"),
        nullable=False,
        default=DocumentVersionStatus.DRAFT,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentApproval(Base):
    """An immutable record of one approve/reject decision on a version. Never
    updated or deleted after creation -- this table, alongside `document_versions`,
    is the QMS audit trail for who approved/rejected what and when (see
    docs/Database.md#soft-delete-and-audit-trail on why a separate generic
    audit_log table was not built for this). `approver_id` references `users.id`,
    not `people.id` -- see
    docs/DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table."""

    __tablename__ = "document_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id"), nullable=False
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(
        _native_enum(ApprovalDecision, "document_approval_decision"), nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
