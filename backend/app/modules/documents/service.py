"""Business logic for the Document Management module: categories, tags, documents,
and (this slice) version file upload/download/preview. Per
docs/modules/DocumentManagement.md and the Milestone 2 plan
(.hermes/plans/2026-07-26-milestone-2-document-management.md): every operation is
scoped to the caller's organisation; `documents.number` is always server-generated;
`owner_id` is validated against the People module's own service (module boundary
rule -- see docs/CodingStandards.md#backend-python), never queried directly.
"""

import datetime
import uuid
from pathlib import Path
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import (
    Document,
    DocumentCategory,
    DocumentStatus,
    DocumentTag,
    DocumentTagLink,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.modules.documents.numbering import generate_document_number
from app.modules.documents.storage import (
    CONTENT_TYPE_BY_EXTENSION,
    build_storage_key,
    extension_for_filename,
    resolve_path,
    sanitise_filename,
    save_validated_upload,
    validate_extension,
)
from app.modules.documents.upload_policy import get_upload_policy
from app.modules.people.service import PersonNotFoundError, get_person


class _UploadFileLike(Protocol):
    filename: str | None

    async def read(self, size: int) -> bytes: ...


class CategoryNotFoundError(Exception):
    """Raised when a category id doesn't exist in the caller's organisation."""


class CategoryHasChildrenError(Exception):
    """Raised when deleting a category that still has child categories."""


class CategoryInUseError(Exception):
    """Raised when deleting a category that is still referenced by a document."""


class TagNotFoundError(Exception):
    """Raised when a tag id doesn't exist in the caller's organisation."""


class TagAlreadyExistsError(Exception):
    """Raised when creating a tag whose name already exists in the organisation."""


class DocumentNotFoundError(Exception):
    """Raised when a document id doesn't exist (or is soft-deleted) in the caller's
    organisation."""


class OwnerNotFoundError(Exception):
    """Raised when a document's `owner_id` doesn't exist (as a person) in the
    caller's organisation."""


class DocumentVersionNotFoundError(Exception):
    """Raised when a version id doesn't exist for the given document (which is
    itself already scoped to the caller's organisation)."""


# --- Categories --------------------------------------------------------------


async def create_category(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    name: str,
    parent_category_id: uuid.UUID | None,
) -> DocumentCategory:
    if parent_category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=parent_category_id)

    category = DocumentCategory(
        organisation_id=organisation_id, name=name, parent_category_id=parent_category_id
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def get_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, category_id: uuid.UUID
) -> DocumentCategory:
    category = (
        await session.execute(
            select(DocumentCategory).where(
                DocumentCategory.id == category_id,
                DocumentCategory.organisation_id == organisation_id,
            )
        )
    ).scalar_one_or_none()
    if category is None:
        raise CategoryNotFoundError(f"No category {category_id} in this organisation")
    return category


async def list_categories(
    session: AsyncSession, *, organisation_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[DocumentCategory], int]:
    total = (
        await session.execute(
            select(func.count())
            .select_from(DocumentCategory)
            .where(DocumentCategory.organisation_id == organisation_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(DocumentCategory)
        .where(DocumentCategory.organisation_id == organisation_id)
        .order_by(DocumentCategory.name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_category(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    category_id: uuid.UUID,
    name: str,
    parent_category_id: uuid.UUID | None,
) -> DocumentCategory:
    category = await get_category(session, organisation_id=organisation_id, category_id=category_id)
    if parent_category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=parent_category_id)
    category.name = name
    category.parent_category_id = parent_category_id
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    category = await get_category(session, organisation_id=organisation_id, category_id=category_id)

    children_count = (
        await session.execute(
            select(func.count())
            .select_from(DocumentCategory)
            .where(DocumentCategory.parent_category_id == category_id)
        )
    ).scalar_one()
    if children_count > 0:
        raise CategoryHasChildrenError("Cannot delete a category that still has child categories")

    documents_count = (
        await session.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.category_id == category_id, Document.deleted_at.is_(None))
        )
    ).scalar_one()
    if documents_count > 0:
        raise CategoryInUseError("Cannot delete a category that is still referenced by a document")

    await session.delete(category)
    await session.commit()


# --- Tags ----------------------------------------------------------------------


async def create_tag(
    session: AsyncSession, *, organisation_id: uuid.UUID, name: str
) -> DocumentTag:
    existing = (
        await session.execute(
            select(DocumentTag).where(
                DocumentTag.organisation_id == organisation_id, DocumentTag.name == name
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise TagAlreadyExistsError(f"A tag named {name!r} already exists in this organisation")

    tag = DocumentTag(organisation_id=organisation_id, name=name)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return tag


async def get_tag(
    session: AsyncSession, *, organisation_id: uuid.UUID, tag_id: uuid.UUID
) -> DocumentTag:
    tag = (
        await session.execute(
            select(DocumentTag).where(
                DocumentTag.id == tag_id, DocumentTag.organisation_id == organisation_id
            )
        )
    ).scalar_one_or_none()
    if tag is None:
        raise TagNotFoundError(f"No tag {tag_id} in this organisation")
    return tag


async def list_tags(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentTag], int]:
    filters = [DocumentTag.organisation_id == organisation_id]
    if search:
        filters.append(DocumentTag.name.ilike(f"%{search}%"))

    total = (
        await session.execute(select(func.count()).select_from(DocumentTag).where(*filters))
    ).scalar_one()
    result = await session.execute(
        select(DocumentTag).where(*filters).order_by(DocumentTag.name).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def delete_tag(
    session: AsyncSession, *, organisation_id: uuid.UUID, tag_id: uuid.UUID
) -> None:
    """Delete a tag, cascading (unlinking) it from every document that used it -- tags
    are lightweight free-form labels, not referential-integrity-critical entities
    like categories, so no "still in use" guard applies here."""
    tag = await get_tag(session, organisation_id=organisation_id, tag_id=tag_id)
    await session.execute(delete(DocumentTagLink).where(DocumentTagLink.tag_id == tag_id))
    await session.delete(tag)
    await session.commit()


async def _validate_owner(
    session: AsyncSession, *, organisation_id: uuid.UUID, owner_id: uuid.UUID
) -> None:
    try:
        await get_person(session, organisation_id=organisation_id, person_id=owner_id)
    except PersonNotFoundError as exc:
        raise OwnerNotFoundError(str(exc)) from exc


async def _resolve_tags(
    session: AsyncSession, *, organisation_id: uuid.UUID, tag_ids: list[uuid.UUID]
) -> list[DocumentTag]:
    tags = []
    for tag_id in tag_ids:
        tags.append(await get_tag(session, organisation_id=organisation_id, tag_id=tag_id))
    return tags


async def list_document_tags(session: AsyncSession, *, document_id: uuid.UUID) -> list[DocumentTag]:
    result = await session.execute(
        select(DocumentTag)
        .join(DocumentTagLink, DocumentTagLink.tag_id == DocumentTag.id)
        .where(DocumentTagLink.document_id == document_id)
        .order_by(DocumentTag.name)
    )
    return list(result.scalars().all())


# --- Documents -------------------------------------------------------------


async def create_document(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    title: str,
    category_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    tag_ids: list[uuid.UUID],
    created_by_id: uuid.UUID | None,
) -> Document:
    if category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=category_id)
    if owner_id is not None:
        await _validate_owner(session, organisation_id=organisation_id, owner_id=owner_id)
    tags = await _resolve_tags(session, organisation_id=organisation_id, tag_ids=tag_ids)

    number = await generate_document_number(session, organisation_id=organisation_id)

    document = Document(
        organisation_id=organisation_id,
        category_id=category_id,
        number=number,
        title=title,
        owner_id=owner_id,
        status=DocumentStatus.DRAFT,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(document)
    await session.flush()

    for tag in tags:
        session.add(DocumentTagLink(document_id=document.id, tag_id=tag.id))

    await session.commit()
    await session.refresh(document)
    return document


async def get_document(
    session: AsyncSession, *, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.organisation_id == organisation_id,
                Document.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise DocumentNotFoundError(f"No document {document_id} in this organisation")
    return document


async def list_documents(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    category_id: uuid.UUID | None,
    status: DocumentStatus | None,
    owner_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    filters = [Document.organisation_id == organisation_id, Document.deleted_at.is_(None)]
    if category_id is not None:
        filters.append(Document.category_id == category_id)
    if status is not None:
        filters.append(Document.status == status)
    if owner_id is not None:
        filters.append(Document.owner_id == owner_id)

    total = (
        await session.execute(select(func.count()).select_from(Document).where(*filters))
    ).scalar_one()
    result = await session.execute(
        select(Document).where(*filters).order_by(Document.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_document(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    updated_by_id: uuid.UUID | None,
    title: str,
    category_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    tag_ids: list[uuid.UUID],
) -> Document:
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    if category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=category_id)
    if owner_id is not None:
        await _validate_owner(session, organisation_id=organisation_id, owner_id=owner_id)
    tags = await _resolve_tags(session, organisation_id=organisation_id, tag_ids=tag_ids)

    document.title = title
    document.category_id = category_id
    document.owner_id = owner_id
    document.updated_by_id = updated_by_id

    await session.execute(delete(DocumentTagLink).where(DocumentTagLink.document_id == document.id))
    for tag in tags:
        session.add(DocumentTagLink(document_id=document.id, tag_id=tag.id))

    await session.commit()
    await session.refresh(document)
    return document


async def delete_document(
    session: AsyncSession, *, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    """Soft-delete: sets `deleted_at`, per docs/Database.md#soft-delete-and-audit-trail.
    The row and its versions' files are retained, never hard-deleted."""
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    document.deleted_at = datetime.datetime.now(datetime.UTC)
    await session.commit()


async def list_document_versions(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[DocumentVersion], int]:
    await get_document(session, organisation_id=organisation_id, document_id=document_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_document_version(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DocumentVersion:
    """Return a version, having first proven the parent document is in the caller's
    own organisation -- file access is always resolved via `(organisation_id,
    document_id, version_id)`, never by `version_id`/`storage_key` alone, so an
    organisation can never reach another organisation's file even with a guessed id."""
    await get_document(session, organisation_id=organisation_id, document_id=document_id)

    version = (
        await session.execute(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id, DocumentVersion.document_id == document_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise DocumentVersionNotFoundError(f"No version {version_id} for document {document_id}")
    return version


async def _next_version_number(session: AsyncSession, *, document_id: uuid.UUID) -> int:
    """Lock the parent `documents` row with `SELECT ... FOR UPDATE` (a no-op on
    SQLite, which has no row-level locking and is single-writer for the unit tests
    that use it) before computing the next version number, so two concurrent
    uploads to the same document under real PostgreSQL serialise instead of racing
    to the same number -- mirrors the same pattern already used for document
    numbering in numbering.py::generate_document_number."""
    lock_statement = select(Document.id).where(Document.id == document_id)
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        lock_statement = lock_statement.with_for_update()
    await session.execute(lock_statement)

    current_max = (
        await session.execute(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.document_id == document_id
            )
        )
    ).scalar_one()
    return (current_max or 0) + 1


async def create_document_version(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    upload: _UploadFileLike,
    change_summary: str | None,
    created_by_id: uuid.UUID | None,
    uploads_dir: Path,
) -> DocumentVersion:
    """Upload a new, immutable version of `document_id`'s file. Treats the upload as
    hostile throughout, per the Milestone 2 plan's "Storage and upload/download/
    preview security" section: the extension is checked against the organisation's
    configured allow-list, the file's own bytes are checked against a magic-byte
    signature where one exists, size is bounded while streaming, and the on-disk
    `storage_key` is entirely server-generated -- never derived from the client's
    filename. Raises `DocumentNotFoundError`, `storage.UnsupportedFileTypeError`,
    `storage.InvalidFileSignatureError`, or `storage.FileTooLargeError`.
    """
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)

    policy = await get_upload_policy(session, organisation_id=organisation_id)

    original_filename = sanitise_filename(upload.filename or "upload")
    extension = extension_for_filename(upload.filename or "")
    validate_extension(extension, policy.allowed_extensions)

    version_number = await _next_version_number(session, document_id=document.id)
    storage_key = build_storage_key(
        organisation_id=organisation_id, document_id=document.id, extension=extension
    )
    destination = resolve_path(uploads_dir, storage_key)

    size_bytes, checksum = await save_validated_upload(
        upload,
        destination=destination,
        max_size_bytes=policy.max_size_bytes,
        extension=extension,
    )

    version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=CONTENT_TYPE_BY_EXTENSION[extension],
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        change_summary=change_summary,
        status=DocumentVersionStatus.DRAFT,
        created_by_id=created_by_id,
    )
    session.add(version)
    try:
        await session.commit()
    except IntegrityError:
        # Belt-and-braces alongside the row lock above: if two uploads to the same
        # document still raced (e.g. under SQLite, which has no real row locking),
        # never leave an orphaned file on disk with no DB row referencing it.
        await session.rollback()
        destination.unlink(missing_ok=True)
        raise
    await session.refresh(version)
    return version
