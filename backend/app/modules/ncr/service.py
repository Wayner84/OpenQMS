"""Business logic for the NCR module: non-conformance reports and their workflow.
Per docs/modules/NCR.md and the Milestone 4 plan
(.hermes/plans/2026-07-29-milestone-4-ncr.md): every operation is scoped to the
caller's organisation; `product_id`, `supplier_id`, and `raised_by_id` are validated
against the Products, Suppliers, and People modules' own service layers (module
boundary rule -- see docs/CodingStandards.md#backend-python), never queried
directly.
"""

import datetime
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.service import DocumentNotFoundError, get_document
from app.modules.ncr.models import (
    NCR_STATUS_SEQUENCE,
    Ncr,
    NcrAction,
    NcrActionStatus,
    NcrAttachment,
    NcrInvestigationTool,
    NcrInvestigationToolType,
    NcrStatus,
    NcrStatusHistory,
    NcrType,
)
from app.modules.ncr.numbering import generate_ncr_number
from app.modules.people.service import PersonNotFoundError, get_person
from app.modules.products.service import ProductNotFoundError, get_product
from app.modules.suppliers.service import SupplierNotFoundError, get_supplier


class NcrNotFoundError(Exception):
    """Raised when an NCR id doesn't exist (or is soft-deleted) in the caller's
    organisation."""


class NcrProductNotFoundError(Exception):
    """Raised when an NCR's `product_id` doesn't exist in the caller's organisation."""


class NcrSupplierNotFoundError(Exception):
    """Raised when an NCR's `supplier_id` doesn't exist in the caller's organisation."""


class NcrRaisedByNotFoundError(Exception):
    """Raised when an NCR's `raised_by_id` doesn't exist in the caller's organisation."""


class InvalidNcrTransitionError(Exception):
    """Raised when a transition's `to_status` is not exactly the next status in the
    fixed sequence for the NCR's current status."""


class NcrCloseBlockedByOpenActionsError(Exception):
    """Raised when transitioning to `closed` while any of the NCR's actions are
    still `open` (design decision 4)."""


class NcrActionNotFoundError(Exception):
    """Raised when an action id doesn't exist for the given NCR."""


class NcrActionsFrozenError(Exception):
    """Raised when adding or editing an action on an NCR that is already
    `closed`. Extends the spirit of design decision 4 (closing is blocked while
    actions are open): once closed, an NCR's actions must stay exactly as they
    were at close time, or the close-blocked-while-actions-open guard could be
    defeated after the fact by reopening a completed action post-closure."""


class NcrActionOwnerNotFoundError(Exception):
    """Raised when an action's `owner_id` doesn't exist in the caller's
    organisation."""


class NcrInvestigationToolFrozenError(Exception):
    """Raised when upserting an investigation tool on an NCR that is already
    `closed`. Same reasoning as `NcrActionsFrozenError`: a closed NCR's
    investigation worksheets must stay exactly as they were at close time."""


class NcrAttachmentNotFoundError(Exception):
    """Raised when an attachment id doesn't exist for the given NCR."""


class NcrAttachmentDocumentNotFoundError(Exception):
    """Raised when an attachment's `document_id` doesn't exist in the caller's
    organisation."""


class NcrAttachmentAlreadyExistsError(Exception):
    """Raised when attaching a document to an NCR that already has it attached."""


class NcrAttachmentsFrozenError(Exception):
    """Raised when adding or removing an attachment on an NCR that is already
    `closed`. Same reasoning as `NcrActionsFrozenError`/
    `NcrInvestigationToolFrozenError`: a closed NCR's evidence must stay exactly
    as it was at close time."""


async def _validate_links(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    raised_by_id: uuid.UUID,
) -> None:
    if product_id is not None:
        try:
            await get_product(session, organisation_id=organisation_id, product_id=product_id)
        except ProductNotFoundError as exc:
            raise NcrProductNotFoundError(str(exc)) from exc
    if supplier_id is not None:
        try:
            await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
        except SupplierNotFoundError as exc:
            raise NcrSupplierNotFoundError(str(exc)) from exc
    try:
        await get_person(session, organisation_id=organisation_id, person_id=raised_by_id)
    except PersonNotFoundError as exc:
        raise NcrRaisedByNotFoundError(str(exc)) from exc


async def create_ncr(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    type: NcrType,
    product_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    raised_by_id: uuid.UUID,
    description: str,
    root_cause_summary: str | None,
    created_by_id: uuid.UUID,
) -> Ncr:
    await _validate_links(
        session,
        organisation_id=organisation_id,
        product_id=product_id,
        supplier_id=supplier_id,
        raised_by_id=raised_by_id,
    )
    number = await generate_ncr_number(session, organisation_id=organisation_id, type=type)

    ncr = Ncr(
        organisation_id=organisation_id,
        number=number,
        type=type,
        product_id=product_id,
        supplier_id=supplier_id,
        status=NcrStatus.OPEN,
        raised_by_id=raised_by_id,
        description=description,
        root_cause_summary=root_cause_summary,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(ncr)
    await session.flush()
    session.add(
        NcrStatusHistory(
            ncr_id=ncr.id,
            from_status=None,
            to_status=NcrStatus.OPEN,
            changed_by_id=created_by_id,
            comments=None,
        )
    )
    await session.commit()
    await session.refresh(ncr)
    return ncr


async def get_ncr(session: AsyncSession, *, organisation_id: uuid.UUID, ncr_id: uuid.UUID) -> Ncr:
    ncr = (
        await session.execute(
            select(Ncr).where(
                Ncr.id == ncr_id,
                Ncr.organisation_id == organisation_id,
                Ncr.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if ncr is None:
        raise NcrNotFoundError(f"No NCR {ncr_id} in this organisation")
    return ncr


async def list_ncrs(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    type: NcrType | None,
    status: NcrStatus | None,
    product_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    raised_by_id: uuid.UUID | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Ncr], int]:
    filters = [Ncr.organisation_id == organisation_id, Ncr.deleted_at.is_(None)]
    if type is not None:
        filters.append(Ncr.type == type)
    if status is not None:
        filters.append(Ncr.status == status)
    if product_id is not None:
        filters.append(Ncr.product_id == product_id)
    if supplier_id is not None:
        filters.append(Ncr.supplier_id == supplier_id)
    if raised_by_id is not None:
        filters.append(Ncr.raised_by_id == raised_by_id)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(Ncr.number.ilike(pattern), Ncr.description.ilike(pattern)))

    total = (
        await session.execute(select(func.count()).select_from(Ncr).where(*filters))
    ).scalar_one()
    result = await session.execute(
        select(Ncr).where(*filters).order_by(Ncr.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_ncr(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    updated_by_id: uuid.UUID,
    type: NcrType,
    product_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    raised_by_id: uuid.UUID,
    description: str,
    root_cause_summary: str | None,
) -> Ncr:
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    await _lock_ncr(session, ncr)
    if ncr.deleted_at is not None:
        # Same re-check as transition_ncr, for the same reason: get_ncr's filter
        # ran before this lock was acquired, and a concurrent admin delete could
        # have committed in between.
        raise NcrNotFoundError(f"No NCR {ncr_id} in this organisation")
    await _validate_links(
        session,
        organisation_id=organisation_id,
        product_id=product_id,
        supplier_id=supplier_id,
        raised_by_id=raised_by_id,
    )

    ncr.type = type
    ncr.product_id = product_id
    ncr.supplier_id = supplier_id
    ncr.raised_by_id = raised_by_id
    ncr.description = description
    ncr.root_cause_summary = root_cause_summary
    ncr.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(ncr)
    return ncr


async def delete_ncr(
    session: AsyncSession, *, organisation_id: uuid.UUID, ncr_id: uuid.UUID
) -> None:
    """Admin-only soft delete (enforced by the router's `CurrentAdmin` dependency),
    per the plan's design decision 2 -- an NCR is an audit-significant record with
    a full status history, unlike Suppliers/Products' hard-deletable reference
    data."""
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    await _lock_ncr(session, ncr)
    ncr.deleted_at = datetime.datetime.now(datetime.UTC)
    await session.commit()


async def _lock_ncr(session: AsyncSession, ncr: Ncr) -> None:
    """Lock `ncr`'s row with `SELECT ... FOR UPDATE` (a no-op on SQLite), then
    refresh its attributes from the now-locked row -- mirrors
    `documents.service._lock_document`. Callers must acquire this lock before
    reading or mutating `ncr.status`/`ncr.deleted_at`, so a concurrent transition
    and delete (or two concurrent transitions) on the same NCR can't both read the
    same stale state and both succeed.

    Also used by `delete_ncr`, so the two operations serialise against each other:
    whichever reaches the lock first commits, and the other observes its committed
    state once it acquires the lock in turn -- see `transition_ncr`'s `deleted_at`
    re-check immediately below the lock, which is what actually rejects a
    transition that lost this race against a concurrent delete."""
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        await session.execute(select(Ncr.id).where(Ncr.id == ncr.id).with_for_update())
    await session.refresh(ncr)


async def transition_ncr(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    to_status: NcrStatus,
    changed_by_id: uuid.UUID,
    comments: str | None,
) -> Ncr:
    """Move `ncr` to exactly the next status in `NCR_STATUS_SEQUENCE`. Raises
    `InvalidNcrTransitionError` if `to_status` is not that next status (no skipping
    stages, no moving backward -- design decision 3)."""
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    await _lock_ncr(session, ncr)
    if ncr.deleted_at is not None:
        # get_ncr's own deleted_at.is_(None) filter ran before the lock was
        # acquired above; a concurrent admin delete could have committed in the
        # window between that read and this lock. Re-check post-lock so a
        # transition can never land on (and add status-history rows to) an NCR
        # that is now soft-deleted -- an independent security review found this
        # gap; see docs/DecisionLog.md.
        raise NcrNotFoundError(f"No NCR {ncr_id} in this organisation")

    current_index = NCR_STATUS_SEQUENCE.index(ncr.status)
    if current_index == len(NCR_STATUS_SEQUENCE) - 1:
        raise InvalidNcrTransitionError(f"NCR {ncr_id} is already closed")
    expected_next = NCR_STATUS_SEQUENCE[current_index + 1]
    if to_status != expected_next:
        raise InvalidNcrTransitionError(
            f"NCR {ncr_id} is {ncr.status.value}; the only valid next status is"
            f" {expected_next.value}, not {to_status.value}"
        )

    if to_status == NcrStatus.CLOSED:
        # Design decision 4: closing is blocked while any action is still open.
        # Checked inside this same locked transaction (the lock was already
        # acquired above, before this read) so a concurrent "add an open action"
        # and "close the NCR" can't race past each other -- whichever commits
        # first is what the other observes.
        open_actions = (
            await session.execute(
                select(func.count())
                .select_from(NcrAction)
                .where(NcrAction.ncr_id == ncr.id, NcrAction.status == NcrActionStatus.OPEN)
            )
        ).scalar_one()
        if open_actions > 0:
            raise NcrCloseBlockedByOpenActionsError(
                f"NCR {ncr_id} cannot close while {open_actions} action(s) are still open"
            )

    from_status = ncr.status
    ncr.status = to_status
    ncr.updated_by_id = changed_by_id
    if to_status == NcrStatus.CLOSED:
        ncr.closed_at = datetime.datetime.now(datetime.UTC)

    session.add(
        NcrStatusHistory(
            ncr_id=ncr.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_id=changed_by_id,
            comments=comments,
        )
    )
    await session.commit()
    await session.refresh(ncr)
    return ncr


async def list_status_history(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[NcrStatusHistory], int]:
    await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(NcrStatusHistory)
            .where(NcrStatusHistory.ncr_id == ncr_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(NcrStatusHistory)
        .where(NcrStatusHistory.ncr_id == ncr_id)
        .order_by(NcrStatusHistory.changed_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


# --- Actions -----------------------------------------------------------------


async def _validate_action_owner(
    session: AsyncSession, *, organisation_id: uuid.UUID, owner_id: uuid.UUID | None
) -> None:
    if owner_id is None:
        return
    try:
        await get_person(session, organisation_id=organisation_id, person_id=owner_id)
    except PersonNotFoundError as exc:
        raise NcrActionOwnerNotFoundError(str(exc)) from exc


async def create_action(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    description: str,
    owner_id: uuid.UUID | None,
    due_date: datetime.date | None,
    created_by_id: uuid.UUID,
) -> NcrAction:
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    # Lock the parent NCR row (same lock transition_ncr's close guard takes)
    # before adding a new open action -- otherwise a concurrent "close the NCR"
    # request's open-actions count could run (and see zero) before this insert
    # commits, letting the NCR close with an action that is about to become open.
    # An independent security review found this gap; see docs/DecisionLog.md.
    await _lock_ncr(session, ncr)
    if ncr.status == NcrStatus.CLOSED:
        raise NcrActionsFrozenError(f"NCR {ncr_id} is closed; its actions cannot be edited")
    await _validate_action_owner(session, organisation_id=organisation_id, owner_id=owner_id)

    action = NcrAction(
        ncr_id=ncr_id,
        description=description,
        owner_id=owner_id,
        due_date=due_date,
        status=NcrActionStatus.OPEN,
        created_by_id=created_by_id,
    )
    session.add(action)
    await session.commit()
    await session.refresh(action)
    return action


async def list_actions(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[NcrAction], int]:
    await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)

    total = (
        await session.execute(
            select(func.count()).select_from(NcrAction).where(NcrAction.ncr_id == ncr_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(NcrAction)
        .where(NcrAction.ncr_id == ncr_id)
        .order_by(NcrAction.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_action(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    action_id: uuid.UUID,
    description: str,
    owner_id: uuid.UUID | None,
    due_date: datetime.date | None,
    status: NcrActionStatus,
) -> NcrAction:
    """Looked up directly by `action_id` (matching the plan's
    `PATCH /api/v1/ncr/actions/{id}` shape, not nested under a specific NCR id),
    but still scoped to the caller's organisation via a join through `ncrs` so a
    cross-organisation action id 404s rather than leaking."""
    action = (
        await session.execute(
            select(NcrAction)
            .join(Ncr, Ncr.id == NcrAction.ncr_id)
            .where(
                NcrAction.id == action_id,
                Ncr.organisation_id == organisation_id,
                Ncr.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if action is None:
        raise NcrActionNotFoundError(f"No action {action_id} in this organisation")

    # Same lock as create_action, for the same reason: without it, a concurrent
    # transition_ncr close-guard count could run in between this read and this
    # commit and miss a status flip happening right now (e.g. this call reopening
    # an action while a transition-to-closed request is simultaneously counting
    # open actions as zero).
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=action.ncr_id)
    await _lock_ncr(session, ncr)
    if ncr.status == NcrStatus.CLOSED:
        raise NcrActionsFrozenError(f"NCR {ncr.id} is closed; its actions cannot be edited")

    await _validate_action_owner(session, organisation_id=organisation_id, owner_id=owner_id)

    was_open = action.status == NcrActionStatus.OPEN
    action.description = description
    action.owner_id = owner_id
    action.due_date = due_date
    action.status = status
    if status == NcrActionStatus.COMPLETE and was_open:
        action.completed_at = datetime.datetime.now(datetime.UTC)
    elif status == NcrActionStatus.OPEN:
        action.completed_at = None

    await session.commit()
    await session.refresh(action)
    return action


# --- Investigation tools ----------------------------------------------------------


async def get_investigation_tool(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    tool_type: NcrInvestigationToolType,
) -> NcrInvestigationTool | None:
    """Returns `None` if this tool has never been saved for this NCR -- "not
    started" is a normal state for an optional aid, not a `404` (the caller
    constructs a default empty payload). Still raises `NcrNotFoundError` if the
    NCR itself doesn't exist in the caller's organisation."""
    await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    return (
        await session.execute(
            select(NcrInvestigationTool).where(
                NcrInvestigationTool.ncr_id == ncr_id,
                NcrInvestigationTool.tool_type == tool_type,
            )
        )
    ).scalar_one_or_none()


async def upsert_investigation_tool(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    tool_type: NcrInvestigationToolType,
    data: dict[str, object],
    updated_by_id: uuid.UUID,
) -> NcrInvestigationTool:
    """Create-or-replace `data` for `(ncr_id, tool_type)` -- see the plan's design
    decision 7. Two concurrent `PUT`s racing to create the same pair are resolved
    by the DB's own unique constraint plus a fallback update, matching `PUT`'s
    replace semantics (last write wins), not an error -- the same
    idempotent-write pattern already used by
    `documents.service.acknowledge_document_version`. Rejects (`409`) once the
    parent NCR is `closed` -- matching `create_action`/`update_action`'s
    frozen-once-closed rule (design decision 4's spirit): an independent security
    review found this slice had no equivalent guard, which would otherwise let a
    closed NCR's investigation worksheet be silently rewritten after closure."""
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    if ncr.status == NcrStatus.CLOSED:
        raise NcrInvestigationToolFrozenError(
            f"NCR {ncr_id} is closed; its investigation tools cannot be edited"
        )

    existing = (
        await session.execute(
            select(NcrInvestigationTool).where(
                NcrInvestigationTool.ncr_id == ncr_id,
                NcrInvestigationTool.tool_type == tool_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.data = data
        existing.updated_by_id = updated_by_id
        await session.commit()
        await session.refresh(existing)
        return existing

    tool = NcrInvestigationTool(
        ncr_id=ncr_id,
        tool_type=tool_type,
        data=data,
        created_by_id=updated_by_id,
        updated_by_id=updated_by_id,
    )
    session.add(tool)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(
                select(NcrInvestigationTool).where(
                    NcrInvestigationTool.ncr_id == ncr_id,
                    NcrInvestigationTool.tool_type == tool_type,
                )
            )
        ).scalar_one()
        existing.data = data
        existing.updated_by_id = updated_by_id
        await session.commit()
        await session.refresh(existing)
        return existing
    await session.refresh(tool)
    return tool


# --- Attachments -------------------------------------------------------------


async def create_attachment(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    document_id: uuid.UUID,
    description: str | None,
    created_by_id: uuid.UUID,
) -> NcrAttachment:
    """Attach a Document Management record as supporting evidence. Locks the
    parent NCR (matching `create_action`'s reasoning) and rejects (`409`) once
    the NCR is `closed` -- a closed NCR's evidence must stay exactly as it was
    at close time, same as its actions and investigation tools."""
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    await _lock_ncr(session, ncr)
    if ncr.status == NcrStatus.CLOSED:
        raise NcrAttachmentsFrozenError(f"NCR {ncr_id} is closed; its attachments cannot be edited")

    try:
        await get_document(session, organisation_id=organisation_id, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise NcrAttachmentDocumentNotFoundError(str(exc)) from exc

    existing = (
        await session.execute(
            select(NcrAttachment).where(
                NcrAttachment.ncr_id == ncr_id, NcrAttachment.document_id == document_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise NcrAttachmentAlreadyExistsError("This document is already attached to the NCR")

    attachment = NcrAttachment(
        ncr_id=ncr_id,
        document_id=document_id,
        description=description,
        created_by_id=created_by_id,
    )
    session.add(attachment)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Belt-and-braces alongside the check above, matching the Products
        # link-table precedent: two concurrent attach requests for the same
        # (ncr_id, document_id) can both pass the check before either commits.
        await session.rollback()
        raise NcrAttachmentAlreadyExistsError(
            "This document is already attached to the NCR"
        ) from exc
    await session.refresh(attachment)
    return attachment


async def list_attachments(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[NcrAttachment], int]:
    await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)

    total = (
        await session.execute(
            select(func.count()).select_from(NcrAttachment).where(NcrAttachment.ncr_id == ncr_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(NcrAttachment)
        .where(NcrAttachment.ncr_id == ncr_id)
        .order_by(NcrAttachment.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def delete_attachment(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> None:
    ncr = await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)
    await _lock_ncr(session, ncr)
    if ncr.status == NcrStatus.CLOSED:
        raise NcrAttachmentsFrozenError(f"NCR {ncr_id} is closed; its attachments cannot be edited")

    attachment = (
        await session.execute(
            select(NcrAttachment).where(
                NcrAttachment.id == attachment_id, NcrAttachment.ncr_id == ncr_id
            )
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise NcrAttachmentNotFoundError(f"No attachment {attachment_id} for NCR {ncr_id}")

    await session.delete(attachment)
    await session.commit()
