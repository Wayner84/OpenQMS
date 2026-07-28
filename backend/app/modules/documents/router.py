"""Document Management endpoints: categories, tags, documents, and (this slice)
version upload/download/preview.

Per docs/API.md and the Milestone 2 plan's "Permissions summary": listing/viewing,
document create/edit, and version upload are open to any active user; category/tag
mutation and document deletion are admin-only. Download/preview re-verify the
caller's organisation owns the parent document on every request -- file access is
never resolved from a raw path or `storage_key`, only via `(document_id,
version_id)` scoped to `current_user.organisation_id` (see
app/modules/documents/service.py::get_document_version).
"""

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.deps import CurrentAdmin, CurrentUser
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.schemas import (
    ApprovalDecisionRequest,
    CategoryListResponse,
    CategoryRead,
    CategoryWriteRequest,
    DocumentAcknowledgementListResponse,
    DocumentAcknowledgementRead,
    DocumentListResponse,
    DocumentRead,
    DocumentVersionListResponse,
    DocumentVersionRead,
    DocumentWriteRequest,
    RejectionRequest,
    TagCreateRequest,
    TagListResponse,
    TagRead,
    VersionComparisonResponse,
)
from app.modules.documents.service import (
    CategoryCycleError,
    CategoryHasChildrenError,
    CategoryInUseError,
    CategoryNotFoundError,
    DocumentNotFoundError,
    DocumentVersionNotFoundError,
    InvalidVersionStateError,
    OwnerNotFoundError,
    RejectionCommentRequiredError,
    TagAlreadyExistsError,
    TagNotFoundError,
    VersionFileMissingError,
    acknowledge_document_version,
    approve_document_version,
    compare_document_versions,
    create_category,
    create_document,
    create_document_version,
    create_tag,
    delete_category,
    delete_document,
    delete_tag,
    get_category,
    get_document,
    get_document_version,
    list_categories,
    list_document_tags,
    list_document_version_acknowledgements,
    list_document_versions,
    list_documents,
    list_tags,
    reject_document_version,
    retire_document,
    submit_document_version_for_approval,
    update_category,
    update_document,
)
from app.modules.documents.storage import (
    PREVIEWABLE_CONTENT_TYPES,
    FileTooLargeError,
    InvalidFileSignatureError,
    UnsupportedFileTypeError,
    resolve_path,
)

logger = logging.getLogger(__name__)

categories_router = APIRouter(prefix="/document-categories", tags=["documents"])
tags_router = APIRouter(prefix="/document-tags", tags=["documents"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


async def _document_read(session: AsyncSession, document: Document) -> DocumentRead:
    tags = await list_document_tags(session, document_id=document.id)
    return DocumentRead(
        id=document.id,
        organisation_id=document.organisation_id,
        category_id=document.category_id,
        number=document.number,
        title=document.title,
        owner_id=document.owner_id,
        status=document.status,
        current_version_id=document.current_version_id,
        created_by_id=document.created_by_id,
        updated_by_id=document.updated_by_id,
        tags=[TagRead.model_validate(tag) for tag in tags],
    )


# --- Categories --------------------------------------------------------------


@categories_router.post("", status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(
    payload: CategoryWriteRequest, current_user: CurrentAdmin, session: SessionDependency
) -> CategoryRead:
    try:
        category = await create_category(
            session,
            organisation_id=current_user.organisation_id,
            name=payload.name,
            parent_category_id=payload.parent_category_id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found"
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.get("")
async def list_categories_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CategoryListResponse:
    categories, total = await list_categories(
        session, organisation_id=current_user.organisation_id, limit=limit, offset=offset
    )
    return CategoryListResponse(
        items=[CategoryRead.model_validate(c) for c in categories],
        total=total,
        limit=limit,
        offset=offset,
    )


@categories_router.get("/{category_id}")
async def get_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> CategoryRead:
    try:
        category = await get_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.patch("/{category_id}")
async def update_category_endpoint(
    category_id: uuid.UUID,
    payload: CategoryWriteRequest,
    current_user: CurrentAdmin,
    session: SessionDependency,
) -> CategoryRead:
    try:
        category = await update_category(
            session,
            organisation_id=current_user.organisation_id,
            category_id=category_id,
            name=payload.name,
            parent_category_id=payload.parent_category_id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except CategoryCycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except (CategoryHasChildrenError, CategoryInUseError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# --- Tags ------------------------------------------------------------------


@tags_router.post("", status_code=status.HTTP_201_CREATED)
async def create_tag_endpoint(
    payload: TagCreateRequest, current_user: CurrentAdmin, session: SessionDependency
) -> TagRead:
    try:
        tag = await create_tag(
            session, organisation_id=current_user.organisation_id, name=payload.name
        )
    except TagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TagRead.model_validate(tag)


@tags_router.get("")
async def list_tags_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TagListResponse:
    tags, total = await list_tags(
        session,
        organisation_id=current_user.organisation_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TagListResponse(
        items=[TagRead.model_validate(t) for t in tags], total=total, limit=limit, offset=offset
    )


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag_endpoint(
    tag_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_tag(session, organisation_id=current_user.organisation_id, tag_id=tag_id)
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc


# --- Documents ---------------------------------------------------------------


@documents_router.post("", status_code=status.HTTP_201_CREATED)
async def create_document_endpoint(
    payload: DocumentWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> DocumentRead:
    try:
        document = await create_document(
            session,
            organisation_id=current_user.organisation_id,
            title=payload.title,
            category_id=payload.category_id,
            owner_id=payload.owner_id,
            tag_ids=payload.tag_ids,
            created_by_id=current_user.id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found"
        ) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc
    return await _document_read(session, document)


@documents_router.get("")
async def list_documents_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    category_id: uuid.UUID | None = None,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    owner_id: uuid.UUID | None = None,
    search: str | None = None,
    tag: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """`search` is a case-insensitive substring match across `title`/`number`;
    `tag` is an exact tag name filter."""
    documents, total = await list_documents(
        session,
        organisation_id=current_user.organisation_id,
        category_id=category_id,
        status=status_filter,
        owner_id=owner_id,
        search=search,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    items = [await _document_read(session, document) for document in documents]
    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@documents_router.get("/{document_id}")
async def get_document_endpoint(
    document_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> DocumentRead:
    try:
        document = await get_document(
            session, organisation_id=current_user.organisation_id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return await _document_read(session, document)


@documents_router.patch("/{document_id}")
async def update_document_endpoint(
    document_id: uuid.UUID,
    payload: DocumentWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> DocumentRead:
    try:
        document = await update_document(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            updated_by_id=current_user.id,
            title=payload.title,
            category_id=payload.category_id,
            owner_id=payload.owner_id,
            tag_ids=payload.tag_ids,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found"
        ) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc
    return await _document_read(session, document)


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_document(
            session, organisation_id=current_user.organisation_id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@documents_router.get("/{document_id}/versions")
async def list_document_versions_endpoint(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentVersionListResponse:
    try:
        versions, total = await list_document_versions(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return DocumentVersionListResponse(
        items=[DocumentVersionRead.model_validate(v) for v in versions],
        total=total,
        limit=limit,
        offset=offset,
    )


@documents_router.post("/{document_id}/versions", status_code=status.HTTP_201_CREATED)
async def upload_document_version_endpoint(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    settings: SettingsDependency,
    file: Annotated[UploadFile, File()],
    change_summary: Annotated[str | None, Form()] = None,
) -> DocumentVersionRead:
    """Upload a new, immutable version. Any active user in the organisation may
    upload -- the approval workflow (a later Milestone 2 slice), not this endpoint,
    is the actual QMS control gate."""
    try:
        version = await create_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            upload=file,
            change_summary=change_summary,
            created_by_id=current_user.id,
            uploads_dir=Path(settings.uploads_dir),
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except InvalidFileSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    return DocumentVersionRead.model_validate(version)


@documents_router.get("/{document_id}/versions/{version_id}/download")
async def download_document_version_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FileResponse:
    try:
        version = await get_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc

    path = resolve_path(Path(settings.uploads_dir), version.storage_key)
    return FileResponse(
        path,
        media_type=version.content_type,
        filename=version.original_filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@documents_router.get("/{document_id}/versions/{version_id}/preview")
async def preview_document_version_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    settings: SettingsDependency,
) -> FileResponse:
    try:
        version = await get_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc

    if version.content_type not in PREVIEWABLE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Preview is not available for this file type; use download instead",
        )

    path = resolve_path(Path(settings.uploads_dir), version.storage_key)
    return FileResponse(
        path,
        media_type=version.content_type,
        filename=version.original_filename,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@documents_router.post("/{document_id}/versions/{version_id}/submit-for-approval")
async def submit_document_version_for_approval_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> DocumentVersionRead:
    """`draft` -> `in_review`. Any active user may submit -- the approve/reject
    endpoints below, not this one, are the actual QMS control gate."""
    try:
        version = await submit_document_version_for_approval(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    except InvalidVersionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return DocumentVersionRead.model_validate(version)


@documents_router.post("/{document_id}/versions/{version_id}/approve")
async def approve_document_version_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    current_user: CurrentAdmin,
    session: SessionDependency,
) -> DocumentVersionRead:
    """`in_review` -> `approved`; supersedes the document's previous current
    version. **Admin only** -- the trust boundary this milestone's two-role model
    gates approval behind (see the plan's permissions summary)."""
    try:
        version = await approve_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
            approver_id=current_user.id,
            comments=payload.comments,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    except InvalidVersionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return DocumentVersionRead.model_validate(version)


@documents_router.post("/{document_id}/versions/{version_id}/reject")
async def reject_document_version_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: RejectionRequest,
    current_user: CurrentAdmin,
    session: SessionDependency,
) -> DocumentVersionRead:
    """`in_review` -> `rejected` (terminal for this version). **Admin only**."""
    try:
        version = await reject_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
            approver_id=current_user.id,
            comments=payload.comments,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    except InvalidVersionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RejectionCommentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return DocumentVersionRead.model_validate(version)


@documents_router.post("/{document_id}/obsolete")
async def retire_document_endpoint(
    document_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> DocumentRead:
    """Retire a whole document (`documents.status` -> `obsolete`), independent of
    its versions' own statuses. **Admin only**."""
    try:
        document = await retire_document(
            session, organisation_id=current_user.organisation_id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return await _document_read(session, document)


@documents_router.post("/{document_id}/versions/{version_id}/acknowledge")
async def acknowledge_document_version_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> DocumentAcknowledgementRead:
    """Record that the caller has read and understood this version. Idempotent --
    acknowledging twice returns the original record, not an error."""
    try:
        acknowledgement = await acknowledge_document_version(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
            acknowledged_by_id=current_user.id,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    return DocumentAcknowledgementRead.model_validate(acknowledgement)


@documents_router.get("/{document_id}/versions/{version_id}/acknowledgements")
async def list_document_version_acknowledgements_endpoint(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentAcknowledgementListResponse:
    """Who has acknowledged this version, and when -- any active user may view
    this (useful for confirming staff have read a controlled document)."""
    try:
        acknowledgements, total = await list_document_version_acknowledgements(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_id=version_id,
            limit=limit,
            offset=offset,
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    return DocumentAcknowledgementListResponse(
        items=[DocumentAcknowledgementRead.model_validate(a) for a in acknowledgements],
        total=total,
        limit=limit,
        offset=offset,
    )


@documents_router.get("/{document_id}/versions/{version_a_id}/compare/{version_b_id}")
async def compare_document_versions_endpoint(
    document_id: uuid.UUID,
    version_a_id: uuid.UUID,
    version_b_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    settings: SettingsDependency,
) -> VersionComparisonResponse:
    """A practical comparison: version-level metadata always; a line-level unified
    text diff when both versions are text-based, otherwise just whether the
    binary content changed (by checksum)."""
    try:
        result = await compare_document_versions(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            uploads_dir=Path(settings.uploads_dir),
        )
    except (DocumentNotFoundError, DocumentVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        ) from exc
    except VersionFileMissingError as exc:
        # Never leak the internal exception text/path to the client, per
        # docs/Architecture.md#security-baseline -- log it server-side and return
        # a generic message.
        logger.error("Document version file missing from storage: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compare these versions right now",
        ) from exc
    return VersionComparisonResponse(
        version_a=DocumentVersionRead.model_validate(result.version_a),
        version_b=DocumentVersionRead.model_validate(result.version_b),
        checksum_changed=result.checksum_changed,
        text_diff=result.text_diff,
    )
