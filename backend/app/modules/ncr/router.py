"""NCR endpoints: non-conformance reports and their workflow.

Per docs/API.md and the Milestone 4 plan's design decision 2: everyday NCR work
(create, view, edit, transition) requires only authentication (any active user),
matching the People/Products/Suppliers precedent. Deleting an NCR is admin-only,
since an NCR is an audit-significant record with a full status history, unlike
Suppliers/Products' pure reference data. Every guard is still fully re-enforced
server-side and scoped to `current_user.organisation_id`, never a client-supplied
value.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentAdmin, CurrentUser
from app.modules.ncr.export import gather_ncr_export_data, render_ncr_pdf
from app.modules.ncr.models import NcrInvestigationToolType, NcrStatus, NcrType
from app.modules.ncr.schemas import (
    NcrActionCreateRequest,
    NcrActionListResponse,
    NcrActionRead,
    NcrActionUpdateRequest,
    NcrAttachmentCreateRequest,
    NcrAttachmentListResponse,
    NcrAttachmentRead,
    NcrCreateRequest,
    NcrInvestigationToolRead,
    NcrInvestigationToolUpsertRequest,
    NcrListResponse,
    NcrRead,
    NcrStatusHistoryListResponse,
    NcrStatusHistoryRead,
    NcrTransitionRequest,
    NcrUpdateRequest,
)
from app.modules.ncr.service import (
    InvalidNcrTransitionError,
    NcrActionNotFoundError,
    NcrActionOwnerNotFoundError,
    NcrActionsFrozenError,
    NcrAttachmentAlreadyExistsError,
    NcrAttachmentDocumentNotFoundError,
    NcrAttachmentNotFoundError,
    NcrAttachmentsFrozenError,
    NcrCloseBlockedByOpenActionsError,
    NcrFrozenError,
    NcrInvestigationToolFrozenError,
    NcrNotFoundError,
    NcrProductNotFoundError,
    NcrRaisedByNotFoundError,
    NcrSupplierNotFoundError,
    create_action,
    create_attachment,
    create_ncr,
    delete_attachment,
    delete_ncr,
    get_investigation_tool,
    get_ncr,
    list_actions,
    list_attachments,
    list_ncrs,
    list_status_history,
    transition_ncr,
    update_action,
    update_ncr,
    upsert_investigation_tool,
)

router = APIRouter(prefix="/ncr", tags=["ncr"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ncr_endpoint(
    payload: NcrCreateRequest, current_user: CurrentUser, session: SessionDependency
) -> NcrRead:
    try:
        ncr = await create_ncr(
            session,
            organisation_id=current_user.organisation_id,
            type=payload.type,
            product_id=payload.product_id,
            supplier_id=payload.supplier_id,
            raised_by_id=payload.raised_by_id,
            description=payload.description,
            root_cause_summary=payload.root_cause_summary,
            created_by_id=current_user.id,
        )
    except NcrProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    except NcrSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except NcrRaisedByNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    return NcrRead.model_validate(ncr)


@router.get("")
async def list_ncrs_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    type: NcrType | None = None,
    status_filter: Annotated[NcrStatus | None, Query(alias="status")] = None,
    product_id: uuid.UUID | None = None,
    supplier_id: uuid.UUID | None = None,
    raised_by_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NcrListResponse:
    ncrs, total = await list_ncrs(
        session,
        organisation_id=current_user.organisation_id,
        type=type,
        status=status_filter,
        product_id=product_id,
        supplier_id=supplier_id,
        raised_by_id=raised_by_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return NcrListResponse(
        items=[NcrRead.model_validate(n) for n in ncrs], total=total, limit=limit, offset=offset
    )


@router.get("/{ncr_id}")
async def get_ncr_endpoint(
    ncr_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> NcrRead:
    try:
        ncr = await get_ncr(session, organisation_id=current_user.organisation_id, ncr_id=ncr_id)
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    return NcrRead.model_validate(ncr)


@router.patch("/{ncr_id}")
async def update_ncr_endpoint(
    ncr_id: uuid.UUID,
    payload: NcrUpdateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrRead:
    try:
        ncr = await update_ncr(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            updated_by_id=current_user.id,
            type=payload.type,
            product_id=payload.product_id,
            supplier_id=payload.supplier_id,
            raised_by_id=payload.raised_by_id,
            description=payload.description,
            root_cause_summary=payload.root_cause_summary,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except NcrProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    except NcrSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except NcrRaisedByNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except NcrFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrRead.model_validate(ncr)


@router.delete("/{ncr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ncr_endpoint(
    ncr_id: uuid.UUID, current_admin: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_ncr(session, organisation_id=current_admin.organisation_id, ncr_id=ncr_id)
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc


@router.post("/{ncr_id}/transition")
async def transition_ncr_endpoint(
    ncr_id: uuid.UUID,
    payload: NcrTransitionRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrRead:
    try:
        ncr = await transition_ncr(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            to_status=payload.to_status,
            changed_by_id=current_user.id,
            comments=payload.comments,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except InvalidNcrTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except NcrCloseBlockedByOpenActionsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrRead.model_validate(ncr)


@router.get("/{ncr_id}/status-history")
async def list_status_history_endpoint(
    ncr_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NcrStatusHistoryListResponse:
    try:
        entries, total = await list_status_history(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            limit=limit,
            offset=offset,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    return NcrStatusHistoryListResponse(
        items=[NcrStatusHistoryRead.model_validate(e) for e in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{ncr_id}/export")
async def export_ncr_endpoint(
    ncr_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    format: Annotated[str, Query()] = "pdf",
) -> Response:
    if format != "pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only format=pdf is supported",
        )
    try:
        data = await gather_ncr_export_data(
            session, organisation_id=current_user.organisation_id, ncr_id=ncr_id
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    pdf_bytes = render_ncr_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{data.ncr.number}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- Actions -----------------------------------------------------------------


@router.post("/{ncr_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_action_endpoint(
    ncr_id: uuid.UUID,
    payload: NcrActionCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrActionRead:
    try:
        action = await create_action(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            description=payload.description,
            owner_id=payload.owner_id,
            due_date=payload.due_date,
            created_by_id=current_user.id,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except NcrActionOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except NcrActionsFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrActionRead.model_validate(action)


@router.get("/{ncr_id}/actions")
async def list_actions_endpoint(
    ncr_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NcrActionListResponse:
    try:
        actions, total = await list_actions(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            limit=limit,
            offset=offset,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    return NcrActionListResponse(
        items=[NcrActionRead.model_validate(a) for a in actions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/actions/{action_id}")
async def update_action_endpoint(
    action_id: uuid.UUID,
    payload: NcrActionUpdateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrActionRead:
    try:
        action = await update_action(
            session,
            organisation_id=current_user.organisation_id,
            action_id=action_id,
            description=payload.description,
            owner_id=payload.owner_id,
            due_date=payload.due_date,
            status=payload.status,
        )
    except NcrActionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Action not found"
        ) from exc
    except NcrActionOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except NcrActionsFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrActionRead.model_validate(action)


# --- Investigation tools -----------------------------------------------------


@router.get("/{ncr_id}/tools/{tool_type}")
async def get_investigation_tool_endpoint(
    ncr_id: uuid.UUID,
    tool_type: NcrInvestigationToolType,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrInvestigationToolRead:
    try:
        tool = await get_investigation_tool(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            tool_type=tool_type,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    if tool is None:
        # "Not started" is a normal state for an optional aid, not a 404.
        return NcrInvestigationToolRead(ncr_id=ncr_id, tool_type=tool_type, data={})
    return NcrInvestigationToolRead.model_validate(tool)


@router.put("/{ncr_id}/tools/{tool_type}")
async def upsert_investigation_tool_endpoint(
    ncr_id: uuid.UUID,
    tool_type: NcrInvestigationToolType,
    payload: NcrInvestigationToolUpsertRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrInvestigationToolRead:
    try:
        tool = await upsert_investigation_tool(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            tool_type=tool_type,
            data=payload.data,
            updated_by_id=current_user.id,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except NcrInvestigationToolFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrInvestigationToolRead.model_validate(tool)


# --- Attachments ---------------------------------------------------------------


@router.post("/{ncr_id}/attachments", status_code=status.HTTP_201_CREATED)
async def create_attachment_endpoint(
    ncr_id: uuid.UUID,
    payload: NcrAttachmentCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> NcrAttachmentRead:
    try:
        attachment = await create_attachment(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            document_id=payload.document_id,
            description=payload.description,
            created_by_id=current_user.id,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except NcrAttachmentDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except NcrAttachmentAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except NcrAttachmentsFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return NcrAttachmentRead.model_validate(attachment)


@router.get("/{ncr_id}/attachments")
async def list_attachments_endpoint(
    ncr_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NcrAttachmentListResponse:
    try:
        attachments, total = await list_attachments(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            limit=limit,
            offset=offset,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    return NcrAttachmentListResponse(
        items=[NcrAttachmentRead.model_validate(a) for a in attachments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{ncr_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment_endpoint(
    ncr_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> None:
    try:
        await delete_attachment(
            session,
            organisation_id=current_user.organisation_id,
            ncr_id=ncr_id,
            attachment_id=attachment_id,
        )
    except NcrNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NCR not found") from exc
    except NcrAttachmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        ) from exc
    except NcrAttachmentsFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
