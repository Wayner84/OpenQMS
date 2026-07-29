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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentAdmin, CurrentUser
from app.modules.ncr.models import NcrStatus, NcrType
from app.modules.ncr.schemas import (
    NcrCreateRequest,
    NcrListResponse,
    NcrRead,
    NcrStatusHistoryListResponse,
    NcrStatusHistoryRead,
    NcrTransitionRequest,
    NcrUpdateRequest,
)
from app.modules.ncr.service import (
    InvalidNcrTransitionError,
    NcrNotFoundError,
    NcrProductNotFoundError,
    NcrRaisedByNotFoundError,
    NcrSupplierNotFoundError,
    create_ncr,
    delete_ncr,
    get_ncr,
    list_ncrs,
    list_status_history,
    transition_ncr,
    update_ncr,
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
