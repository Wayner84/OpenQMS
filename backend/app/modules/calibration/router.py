"""Calibration and Asset Management endpoints: assets (this slice) and, in later
slices, their calibration schedules/events and maintenance schedules.

Per docs/API.md and the Milestone 5 plan's design decision 1: every operation here
requires only authentication (any active user), not admin privilege -- matching
People/Products/Suppliers/NCR's precedent. Every guard is still fully re-enforced
server-side and scoped to `current_user.organisation_id`, never a client-supplied
value.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser
from app.modules.calibration.models import AssetStatus, AssetType
from app.modules.calibration.schemas import AssetListResponse, AssetRead, AssetWriteRequest
from app.modules.calibration.service import (
    AssetNotFoundError,
    AssetOwnerNotFoundError,
    AssetTagConflictError,
    create_asset,
    delete_asset,
    get_asset,
    list_assets,
    update_asset,
)

router = APIRouter(prefix="/calibration", tags=["calibration"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
    payload: AssetWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> AssetRead:
    try:
        asset = await create_asset(
            session,
            organisation_id=current_user.organisation_id,
            asset_tag=payload.asset_tag,
            name=payload.name,
            asset_type=payload.asset_type,
            serial_number=payload.serial_number,
            location=payload.location,
            owner_id=payload.owner_id,
            status=payload.status,
            purchase_date=payload.purchase_date,
            created_by_id=current_user.id,
        )
    except AssetOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except AssetTagConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AssetRead.model_validate(asset)


@router.get("/assets")
async def list_assets_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    asset_type: AssetType | None = None,
    status_filter: Annotated[AssetStatus | None, Query(alias="status")] = None,
    location: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssetListResponse:
    assets, total = await list_assets(
        session,
        organisation_id=current_user.organisation_id,
        asset_type=asset_type,
        status=status_filter,
        location=location,
        search=search,
        limit=limit,
        offset=offset,
    )
    return AssetListResponse(
        items=[AssetRead.model_validate(a) for a in assets], total=total, limit=limit, offset=offset
    )


@router.get("/assets/{asset_id}")
async def get_asset_endpoint(
    asset_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> AssetRead:
    try:
        asset = await get_asset(
            session, organisation_id=current_user.organisation_id, asset_id=asset_id
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    return AssetRead.model_validate(asset)


@router.patch("/assets/{asset_id}")
async def update_asset_endpoint(
    asset_id: uuid.UUID,
    payload: AssetWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> AssetRead:
    try:
        asset = await update_asset(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            updated_by_id=current_user.id,
            asset_tag=payload.asset_tag,
            name=payload.name,
            asset_type=payload.asset_type,
            serial_number=payload.serial_number,
            location=payload.location,
            owner_id=payload.owner_id,
            status=payload.status,
            purchase_date=payload.purchase_date,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    except AssetOwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except AssetTagConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AssetRead.model_validate(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_endpoint(
    asset_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await delete_asset(session, organisation_id=current_user.organisation_id, asset_id=asset_id)
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
