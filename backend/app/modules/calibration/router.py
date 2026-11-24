"""Calibration and Asset Management endpoints: assets, calibration schedules/events
(this slice), and, in a later slice, maintenance schedules.

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
from app.modules.calibration.maintenance_schemas import (
    MaintenanceScheduleEmpty,
    MaintenanceScheduleRead,
    MaintenanceScheduleUpdateRequest,
    MaintenanceScheduleWrite,
)
from app.modules.calibration.models import AssetStatus, AssetType
from app.modules.calibration.schemas import (
    AssetListResponse,
    AssetRead,
    AssetWriteRequest,
    CalibrationEventCreateRequest,
    CalibrationEventListResponse,
    CalibrationEventRead,
    CalibrationScheduleCreateRequest,
    CalibrationScheduleRead,
    CalibrationScheduleUpdateRequest,
)
from app.modules.calibration.service import (
    AssetMaintenanceScheduleAlreadyExistsError,
    AssetMaintenanceScheduleNotFoundError,
    AssetNotFoundError,
    AssetOwnerNotFoundError,
    AssetTagConflictError,
    CalibrationEventDocumentNotFoundError,
    CalibrationEventPerformerNotFoundError,
    CalibrationEventSupplierNotFoundError,
    CalibrationScheduleAlreadyExistsError,
    CalibrationScheduleNotFoundError,
    create_asset,
    create_event,
    create_maintenance_schedule,
    create_schedule,
    delete_asset,
    get_asset,
    get_maintenance_schedule,
    get_schedule,
    list_assets,
    list_events,
    update_asset,
    update_maintenance_schedule,
    update_schedule,
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


# --- Calibration schedules -----------------------------------------------------


@router.post("/assets/{asset_id}/schedule", status_code=status.HTTP_201_CREATED)
async def create_schedule_endpoint(
    asset_id: uuid.UUID,
    payload: CalibrationScheduleCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> CalibrationScheduleRead:
    try:
        schedule = await create_schedule(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            interval_value=payload.interval_value,
            interval_unit=payload.interval_unit,
            created_by_id=current_user.id,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    except CalibrationScheduleAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CalibrationScheduleRead.model_validate(schedule)


@router.get("/assets/{asset_id}/schedule")
async def get_schedule_endpoint(
    asset_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> CalibrationScheduleRead:
    try:
        schedule = await get_schedule(
            session, organisation_id=current_user.organisation_id, asset_id=asset_id
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    except CalibrationScheduleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CalibrationScheduleRead.model_validate(schedule)


@router.patch("/assets/{asset_id}/schedule")
async def update_schedule_endpoint(
    asset_id: uuid.UUID,
    payload: CalibrationScheduleUpdateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> CalibrationScheduleRead:
    try:
        schedule = await update_schedule(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            updated_by_id=current_user.id,
            interval_value=payload.interval_value,
            interval_unit=payload.interval_unit,
            next_due_date=payload.next_due_date,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    except CalibrationScheduleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CalibrationScheduleRead.model_validate(schedule)


# --- Calibration events ----------------------------------------------------------


@router.post("/assets/{asset_id}/events", status_code=status.HTTP_201_CREATED)
async def create_event_endpoint(
    asset_id: uuid.UUID,
    payload: CalibrationEventCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> CalibrationEventRead:
    try:
        event = await create_event(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            performed_at=payload.performed_at,
            performed_by_id=payload.performed_by_id,
            performed_by_supplier_id=payload.performed_by_supplier_id,
            certificate_document_id=payload.certificate_document_id,
            result=payload.result,
            notes=payload.notes,
            created_by_id=current_user.id,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    except CalibrationScheduleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CalibrationEventPerformerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    except CalibrationEventSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except CalibrationEventDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return CalibrationEventRead.model_validate(event)


@router.get("/assets/{asset_id}/events")
async def list_events_endpoint(
    asset_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CalibrationEventListResponse:
    try:
        events, total = await list_events(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            limit=limit,
            offset=offset,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        ) from exc
    return CalibrationEventListResponse(
        items=[CalibrationEventRead.model_validate(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/assets/{asset_id}/maintenance-schedule")
async def get_maintenance_schedule_endpoint(
    asset_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> MaintenanceScheduleRead | MaintenanceScheduleEmpty:
    try:
        row = await get_maintenance_schedule(
            session, organisation_id=current_user.organisation_id, asset_id=asset_id
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    if row is None:
        return MaintenanceScheduleEmpty(asset_id=asset_id)
    return MaintenanceScheduleRead.model_validate(row)


@router.post("/assets/{asset_id}/maintenance-schedule", status_code=status.HTTP_201_CREATED)
async def create_maintenance_schedule_endpoint(
    asset_id: uuid.UUID,
    payload: MaintenanceScheduleWrite,
    current_user: CurrentUser,
    session: SessionDependency,
) -> MaintenanceScheduleRead:
    try:
        row = await create_maintenance_schedule(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            interval_value=payload.interval_value,
            interval_unit=payload.interval_unit,
            next_due_date=payload.next_due_date,
            created_by_id=current_user.id,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    except AssetMaintenanceScheduleAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MaintenanceScheduleRead.model_validate(row)


@router.patch("/assets/{asset_id}/maintenance-schedule")
async def update_maintenance_schedule_endpoint(
    asset_id: uuid.UUID,
    payload: MaintenanceScheduleUpdateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> MaintenanceScheduleRead:
    try:
        row = await update_maintenance_schedule(
            session,
            organisation_id=current_user.organisation_id,
            asset_id=asset_id,
            interval_value=payload.interval_value,
            interval_unit=payload.interval_unit,
            next_due_date=payload.next_due_date,
            next_due_date_supplied="next_due_date" in payload.model_fields_set,
            updated_by_id=current_user.id,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc
    except AssetMaintenanceScheduleNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MaintenanceScheduleRead.model_validate(row)
