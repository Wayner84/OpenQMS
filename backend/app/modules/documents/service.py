"""Business logic for the Document Management module: categories, tags, documents,
and (this slice) version file upload/download/preview. Per
docs/modules/DocumentManagement.md and the Milestone 2 plan
(.hermes/plans/2026-07-26-milestone-2-document-management.md): every operation is
scoped to the caller's organisation; `documents.number` is always server-generated;
`owner_id` is validated against the People module's own service (module boundary
rule -- see docs/CodingStandards.md#backend-python), never queried directly.
"""

import datetime
import difflib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import (
    ApprovalDecision,
    Document,
    DocumentAcknowledgement,
    DocumentApproval,
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


class CategoryCycleError(Exception):
    """Raised when updating a category's parent would make it its own ancestor
    (setting it to itself, or to one of its own descendants)."""


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


class InvalidVersionStateError(Exception):
    """Raised when a workflow transition is requested for a version that isn't in
    the state that transition requires (e.g. approving a version that's still a
    `draft`, or submitting one that's already `approved`)."""


class RejectionCommentRequiredError(Exception):
    """Raised when rejecting a version without explaining why -- required by the
    service layer (not the database) so the reason is always recorded."""


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


async def _assert_no_category_cycle(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    category_id: uuid.UUID,
    new_parent_id: uuid.UUID,
) -> None:
    """Walk upward from `new_parent_id` toward the root. If `category_id` is
    encountered along the way, setting it as the parent would create a cycle --
    either directly (`new_parent_id == category_id`, caught on the first
    iteration) or indirectly (`new_parent_id` is one of `category_id`'s own
    descendants). Raises `CategoryCycleError` in either case."""
    current_id: uuid.UUID | None = new_parent_id
    seen: set[uuid.UUID] = set()
    while current_id is not None:
        if current_id == category_id:
            raise CategoryCycleError(
                "A category cannot be set as its own ancestor (itself or a descendant as parent)"
            )
        if current_id in seen:
            # Defensive only: this same guard is what prevents a cycle from ever
            # being stored in the first place, so a pre-existing cycle should be
            # unreachable -- but stop rather than loop forever if one somehow exists.
            break
        seen.add(current_id)
        current_id = (
            await session.execute(
                select(DocumentCategory.parent_category_id).where(
                    DocumentCategory.id == current_id,
                    DocumentCategory.organisation_id == organisation_id,
                )
            )
        ).scalar_one_or_none()


async def _lock_category_tree(session: AsyncSession, *, organisation_id: uuid.UUID) -> None:
    """Serialise concurrent category-tree mutations within a single organisation by
    locking every one of its category rows with `SELECT ... FOR UPDATE` (a no-op on
    SQLite, which has no row-level locking and is single-writer for the unit tests
    that use it) before `_assert_no_category_cycle` reads the tree. Without this,
    two concurrent updates -- e.g. A.parent := B and B.parent := A -- can each read
    the tree before the other commits its write, each see no cycle, and both
    succeed, together creating a cycle that neither update alone would have passed
    (a TOCTOU race an independent review of this slice found). Mirrors the same
    dialect-gated row-lock pattern as `_lock_document` above; a Postgres advisory
    lock keyed on `organisation_id` would also work, but locking the rows already
    being read keeps this consistent with the existing pattern instead of
    introducing a second locking mechanism.
    """
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        await session.execute(
            select(DocumentCategory.id)
            .where(DocumentCategory.organisation_id == organisation_id)
            .with_for_update()
        )


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
        await _lock_category_tree(session, organisation_id=organisation_id)
        await _assert_no_category_cycle(
            session,
            organisation_id=organisation_id,
            category_id=category_id,
            new_parent_id=parent_category_id,
        )
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
    search: str | None = None,
    tag: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Document], int]:
    """List documents, optionally filtered by exact `category_id`/`status`/
    `owner_id`, a case-insensitive substring `search` across `title`/`number`, and
    an exact `tag` name (joined through `document_tag_links`/`document_tags`)."""
    filters = [Document.organisation_id == organisation_id, Document.deleted_at.is_(None)]
    if category_id is not None:
        filters.append(Document.category_id == category_id)
    if status is not None:
        filters.append(Document.status == status)
    if owner_id is not None:
        filters.append(Document.owner_id == owner_id)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(Document.title.ilike(pattern), Document.number.ilike(pattern)))

    def _with_tag_join(statement: Select[Any]) -> Select[Any]:
        if not tag:
            return statement
        return (
            statement.join(DocumentTagLink, DocumentTagLink.document_id == Document.id)
            .join(DocumentTag, DocumentTag.id == DocumentTagLink.tag_id)
            # Defense in depth: a tag can only ever be linked to a document in
            # its own organisation (create_document/_resolve_tags enforce this at
            # write time), so this predicate is redundant with the outer
            # Document.organisation_id filter today -- but the join is scoped
            # explicitly anyway rather than relying solely on that write-time
            # invariant, per an independent review of this slice.
            .where(DocumentTag.organisation_id == organisation_id, DocumentTag.name == tag)
        )

    count_query = _with_tag_join(
        select(func.count(func.distinct(Document.id))).select_from(Document).where(*filters)
    )
    total = (await session.execute(count_query)).scalar_one()

    list_query = (
        _with_tag_join(select(Document).where(*filters))
        .order_by(Document.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(list_query)
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
    """Compute the next version number for `document_id`. Callers must already hold
    the document row lock (see `_lock_document` below) -- this function does not
    lock anything itself, so two concurrent uploads to the same document only
    serialise correctly if both went through `_lock_document` first."""
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

    await _lock_document(session, document)
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


# --- Approval workflow -------------------------------------------------------
#
# Per the Milestone 2 plan's "Workflow (state machine)" section: a version moves
# draft -> in_review -> approved (or rejected, terminal for that version -- a new
# version must be created to try again); a later version's approval automatically
# supersedes (-> obsolete) whichever version was previously current. `documents.status`
# is a service-maintained cache, not an independent machine: it becomes (and stays)
# `approved` the moment any version is ever approved -- even while a later revision
# is separately being drafted/reviewed -- and only `in_review`/`draft` before that
# first approval ever happens.


async def _lock_document(session: AsyncSession, document: Document) -> None:
    """Lock `document`'s row with `SELECT ... FOR UPDATE` (a no-op on SQLite, which
    has no row-level locking and is single-writer for the unit tests that use it),
    then refresh its attributes from the now-locked row -- mirrors the same
    concurrency-safety pattern already used for document numbering
    (numbering.py::generate_document_number) and version-number allocation
    (`_next_version_number` below).

    Callers must acquire this lock *before* reading or mutating `document`'s own
    fields (`status`, `current_version_id`) or any `document_versions` row that
    belongs to it, and must fetch/re-check that version's `status` only after the
    lock is held -- otherwise two concurrent workflow transitions on the same
    document (e.g. two admins approving two different `in_review` versions, or
    the same version being approved twice) can both read stale state and both
    succeed, producing two simultaneously-"current" versions or duplicate
    `document_approvals` rows. An independent security review of this workflow
    slice found exactly that race before this helper existed; see
    docs/DecisionLog.md#2026-07-26-document-approval-workflow-a-status-cache-integrity-bug-and-a-toctou-race.
    """
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        await session.execute(
            select(Document.id).where(Document.id == document.id).with_for_update()
        )
    await session.refresh(document)


async def submit_document_version_for_approval(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DocumentVersion:
    """`draft` -> `in_review`. Raises `InvalidVersionStateError` if the version
    isn't currently `draft`."""
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    await _lock_document(session, document)
    version = await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
    )
    if version.status != DocumentVersionStatus.DRAFT:
        raise InvalidVersionStateError(
            f"Version {version_id} is {version.status.value}, not draft"
            " -- cannot submit for approval"
        )

    version.status = DocumentVersionStatus.IN_REVIEW
    # Never touch a retired (obsolete) document's cached status from this
    # any-active-user action -- only the admin-only retire/approve actions may
    # change it, so a member can't silently undo an admin's retire by uploading
    # and submitting a new draft.
    if document.current_version_id is None and document.status != DocumentStatus.OBSOLETE:
        document.status = DocumentStatus.IN_REVIEW

    await session.commit()
    await session.refresh(version)
    return version


async def approve_document_version(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    approver_id: uuid.UUID,
    comments: str | None,
) -> DocumentVersion:
    """`in_review` -> `approved`; supersedes the document's previous current
    version (-> `obsolete`); records a `document_approvals` row. Raises
    `InvalidVersionStateError` if the version isn't currently `in_review`."""
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    await _lock_document(session, document)
    version = await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
    )
    if version.status != DocumentVersionStatus.IN_REVIEW:
        raise InvalidVersionStateError(
            f"Version {version_id} is {version.status.value}, not in_review -- cannot approve"
        )

    previous_current_version_id = document.current_version_id
    if previous_current_version_id is not None and previous_current_version_id != version.id:
        previous_version = (
            await session.execute(
                select(DocumentVersion).where(DocumentVersion.id == previous_current_version_id)
            )
        ).scalar_one_or_none()
        if previous_version is not None:
            previous_version.status = DocumentVersionStatus.OBSOLETE

    version.status = DocumentVersionStatus.APPROVED
    document.current_version_id = version.id
    # An approval is itself an admin action, so (unlike submit/reject above) it is
    # allowed to revive a previously-retired document -- that is a deliberate
    # admin decision, at the same trust level as retiring it in the first place.
    document.status = DocumentStatus.APPROVED

    session.add(
        DocumentApproval(
            document_version_id=version.id,
            approver_id=approver_id,
            decision=ApprovalDecision.APPROVED,
            comments=comments,
        )
    )

    await session.commit()
    await session.refresh(version)
    return version


async def reject_document_version(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    approver_id: uuid.UUID,
    comments: str,
) -> DocumentVersion:
    """`in_review` -> `rejected` (terminal for this version -- a new version must be
    created to try again); records a `document_approvals` row. `comments` is
    required so the reason is always captured. Raises `RejectionCommentRequiredError`
    if blank, or `InvalidVersionStateError` if the version isn't `in_review`."""
    if not comments or not comments.strip():
        raise RejectionCommentRequiredError("A comment explaining the rejection is required")

    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    await _lock_document(session, document)
    version = await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
    )
    if version.status != DocumentVersionStatus.IN_REVIEW:
        raise InvalidVersionStateError(
            f"Version {version_id} is {version.status.value}, not in_review -- cannot reject"
        )

    version.status = DocumentVersionStatus.REJECTED
    # Same reasoning as submit above: never un-retire a document from this
    # any-active-user-reachable action.
    if document.current_version_id is None and document.status != DocumentStatus.OBSOLETE:
        document.status = DocumentStatus.DRAFT

    session.add(
        DocumentApproval(
            document_version_id=version.id,
            approver_id=approver_id,
            decision=ApprovalDecision.REJECTED,
            comments=comments,
        )
    )

    await session.commit()
    await session.refresh(version)
    return version


async def retire_document(
    session: AsyncSession, *, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    """Retire a whole document (`documents.status` -> `obsolete`), independent of
    its versions' own statuses -- the whole-document equivalent of a version being
    superseded, for a document that is no longer in use at all."""
    document = await get_document(session, organisation_id=organisation_id, document_id=document_id)
    document.status = DocumentStatus.OBSOLETE
    await session.commit()
    await session.refresh(document)
    return document


# --- Acknowledgements ----------------------------------------------------------


async def acknowledge_document_version(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    acknowledged_by_id: uuid.UUID,
) -> DocumentAcknowledgement:
    """Record that `acknowledged_by_id` has read and understood this version.
    Idempotent: re-acknowledging an already-acknowledged version returns the
    existing row rather than raising, per the Milestone 2 plan."""
    await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
    )

    existing = (
        await session.execute(
            select(DocumentAcknowledgement).where(
                DocumentAcknowledgement.document_version_id == version_id,
                DocumentAcknowledgement.acknowledged_by_id == acknowledged_by_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    acknowledgement = DocumentAcknowledgement(
        document_version_id=version_id, acknowledged_by_id=acknowledged_by_id
    )
    session.add(acknowledgement)
    try:
        await session.commit()
    except IntegrityError:
        # Two concurrent acknowledge calls for the same (version, user) pair --
        # the unique constraint caught it; treat it the same as the idempotent
        # case above rather than surfacing a spurious error for a non-destructive
        # action.
        await session.rollback()
        existing = (
            await session.execute(
                select(DocumentAcknowledgement).where(
                    DocumentAcknowledgement.document_version_id == version_id,
                    DocumentAcknowledgement.acknowledged_by_id == acknowledged_by_id,
                )
            )
        ).scalar_one()
        return existing
    await session.refresh(acknowledgement)
    return acknowledgement


async def list_document_version_acknowledgements(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[DocumentAcknowledgement], int]:
    await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_id
    )

    total = (
        await session.execute(
            select(func.count())
            .select_from(DocumentAcknowledgement)
            .where(DocumentAcknowledgement.document_version_id == version_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(DocumentAcknowledgement)
        .where(DocumentAcknowledgement.document_version_id == version_id)
        .order_by(DocumentAcknowledgement.acknowledged_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


# --- Version comparison --------------------------------------------------------
#
# Per the Milestone 2 plan's "PDF preview and version comparison" section: a
# practical, not speculative, comparison. Always reports the version-level
# metadata diff; additionally reports a line-level unified text diff when both
# versions have a text-based content type, or otherwise just whether the binary
# content changed (by checksum) -- no PDF/Office structured diffing, which is
# recorded there as a future improvement rather than built speculatively now.

TEXT_COMPARABLE_CONTENT_TYPES = frozenset({"text/plain", "text/csv"})

# Independent review finding: diffing is not streamed, so both files are held
# fully in memory. The per-organisation upload policy already bounds a single
# file's size (default 50 MB), but a text diff of two files anywhere near that
# size is neither a useful UI comparison nor a memory cost worth paying on every
# request. Skip the (expensive, not very readable) diff above this size and fall
# back to the checksum-only comparison instead -- proportionate to this being a
# "practical, not speculative" comparison feature, not a full guard against the
# upload policy's own configured ceiling.
MAX_TEXT_DIFF_BYTES = 5 * 1024 * 1024


class VersionFileMissingError(Exception):
    """Raised when a version's file is missing from disk at comparison time (an
    operational data-integrity problem, not a client error)."""


@dataclass
class VersionComparisonResult:
    version_a: DocumentVersion
    version_b: DocumentVersion
    checksum_changed: bool
    text_diff: list[str] | None


async def compare_document_versions(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    version_a_id: uuid.UUID,
    version_b_id: uuid.UUID,
    uploads_dir: Path,
) -> VersionComparisonResult:
    """Compare two versions of the same document. Raises `DocumentNotFoundError`/
    `DocumentVersionNotFoundError` if either version doesn't exist in the caller's
    own organisation, or `VersionFileMissingError` if a version's file is missing
    from disk."""
    version_a = await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_a_id
    )
    version_b = await get_document_version(
        session, organisation_id=organisation_id, document_id=document_id, version_id=version_b_id
    )

    checksum_changed = version_a.checksum_sha256 != version_b.checksum_sha256

    text_diff: list[str] | None = None
    if (
        version_a.content_type in TEXT_COMPARABLE_CONTENT_TYPES
        and version_b.content_type in TEXT_COMPARABLE_CONTENT_TYPES
        and version_a.size_bytes <= MAX_TEXT_DIFF_BYTES
        and version_b.size_bytes <= MAX_TEXT_DIFF_BYTES
    ):
        path_a = resolve_path(uploads_dir, version_a.storage_key)
        path_b = resolve_path(uploads_dir, version_b.storage_key)
        try:
            text_a = path_a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            text_b = path_b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except FileNotFoundError as exc:
            raise VersionFileMissingError(
                f"A file for document {document_id} is missing from storage"
            ) from exc
        text_diff = list(
            difflib.unified_diff(
                text_a,
                text_b,
                fromfile=f"v{version_a.version_number}",
                tofile=f"v{version_b.version_number}",
            )
        )

    return VersionComparisonResult(
        version_a=version_a,
        version_b=version_b,
        checksum_changed=checksum_changed,
        text_diff=text_diff,
    )
