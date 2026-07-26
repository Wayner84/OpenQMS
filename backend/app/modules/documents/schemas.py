"""Pydantic schemas for the Document Management module (categories, tags, documents),
per docs/API.md and the Milestone 2 plan
(.hermes/plans/2026-07-26-milestone-2-document-management.md).
"""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.documents.models import DocumentStatus, DocumentVersionStatus


class CategoryWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/document-categories."""

    name: str
    parent_category_id: uuid.UUID | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    name: str
    parent_category_id: uuid.UUID | None


class CategoryListResponse(BaseModel):
    items: list[CategoryRead]
    total: int
    limit: int
    offset: int


class TagCreateRequest(BaseModel):
    name: str


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    name: str


class TagListResponse(BaseModel):
    items: list[TagRead]
    total: int
    limit: int
    offset: int


class DocumentWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/documents. `number` is never
    client-supplied -- it is always generated server-side (see
    app/modules/documents/numbering.py)."""

    title: str
    category_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] = []


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    category_id: uuid.UUID | None
    number: str
    title: str
    owner_id: uuid.UUID | None
    status: DocumentStatus
    current_version_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None
    tags: list[TagRead] = []


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    limit: int
    offset: int


class DocumentVersionRead(BaseModel):
    """A version's public shape. `storage_key` is deliberately never included --
    file access only ever goes through the download/preview endpoints, never a raw
    path, per the Milestone 2 plan's upload/download/preview security section."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    change_summary: str | None
    status: DocumentVersionStatus
    created_by_id: uuid.UUID | None
    created_at: datetime.datetime


class DocumentVersionListResponse(BaseModel):
    items: list[DocumentVersionRead]
    total: int
    limit: int
    offset: int


class ApprovalDecisionRequest(BaseModel):
    """Body for POST .../approve. Comments are optional on approval."""

    comments: str | None = None


class RejectionRequest(BaseModel):
    """Body for POST .../reject. `comments` is required at both this schema layer
    and (defensively) the service layer -- a rejection must always explain why."""

    comments: str


class DocumentAcknowledgementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_version_id: uuid.UUID
    acknowledged_by_id: uuid.UUID
    acknowledged_at: datetime.datetime


class DocumentAcknowledgementListResponse(BaseModel):
    items: list[DocumentAcknowledgementRead]
    total: int
    limit: int
    offset: int


class VersionComparisonResponse(BaseModel):
    """Response for GET .../versions/{a}/compare/{b} -- a practical, not
    speculative, comparison. `text_diff` (a unified diff, one line per list entry)
    is present only when both versions have a text-based content type; otherwise
    only `checksum_changed` reports whether the binary content differs."""

    version_a: DocumentVersionRead
    version_b: DocumentVersionRead
    checksum_changed: bool
    text_diff: list[str] | None
