"""Business logic for the Calibration and Asset Management module. Per
docs/modules/CalibrationAndAssetManagement.md and the Milestone 5 plan
(.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md): every
operation is scoped to the caller's organisation; `owner_id` is validated against
the People module's own service layer (module boundary rule -- see
docs/CodingStandards.md#backend-python), never queried directly.
"""

import calendar
import datetime
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calibration.models import (
    Asset,
    AssetStatus,
    AssetType,
    CalibrationEvent,
    CalibrationIntervalUnit,
    CalibrationResult,
    CalibrationSchedule,
)
from app.modules.documents.service import DocumentNotFoundError, get_document
from app.modules.people.service import PersonNotFoundError, get_person
from app.modules.suppliers.service import SupplierNotFoundError, get_supplier


class AssetNotFoundError(Exception):
    """Raised when an asset id doesn't exist (or is soft-deleted) in the caller's
    organisation."""


class AssetTagConflictError(Exception):
    """Raised when creating/updating an asset with an `asset_tag` already used by
    another asset in the same organisation."""


class AssetOwnerNotFoundError(Exception):
    """Raised when an asset's `owner_id` doesn't exist in the caller's organisation."""


class CalibrationScheduleNotFoundError(Exception):
    """Raised when an asset has no calibration schedule yet, or the schedule
    doesn't exist in the caller's organisation."""


class CalibrationScheduleAlreadyExistsError(Exception):
    """Raised when creating a calibration schedule for an asset that already has
    one -- `POST` is create-once; use `PATCH` to change an existing schedule."""


class CalibrationEventPerformerNotFoundError(Exception):
    """Raised when a calibration event's `performed_by_id` doesn't exist in the
    caller's organisation."""


class CalibrationEventSupplierNotFoundError(Exception):
    """Raised when a calibration event's `performed_by_supplier_id` doesn't exist
    in the caller's organisation."""


class CalibrationEventDocumentNotFoundError(Exception):
    """Raised when a calibration event's `certificate_document_id` doesn't exist
    in the caller's organisation."""


async def _assert_asset_tag_available(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_tag: str,
    exclude_asset_id: uuid.UUID | None,
) -> None:
    filters = [
        Asset.organisation_id == organisation_id,
        Asset.asset_tag == asset_tag,
        Asset.deleted_at.is_(None),
    ]
    if exclude_asset_id is not None:
        filters.append(Asset.id != exclude_asset_id)
    existing = (await session.execute(select(Asset).where(*filters))).scalar_one_or_none()
    if existing is not None:
        raise AssetTagConflictError(
            f"An asset with tag {asset_tag!r} already exists in this organisation"
        )


async def _validate_owner(
    session: AsyncSession, *, organisation_id: uuid.UUID, owner_id: uuid.UUID | None
) -> None:
    if owner_id is None:
        return
    try:
        await get_person(session, organisation_id=organisation_id, person_id=owner_id)
    except PersonNotFoundError as exc:
        raise AssetOwnerNotFoundError(str(exc)) from exc


async def _lock_asset(session: AsyncSession, asset: Asset) -> None:
    """Lock `asset`'s row with `SELECT ... FOR UPDATE` (a no-op on SQLite), then
    refresh its attributes from the now-locked row -- mirrors
    `ncr.service._lock_ncr`/`documents.service._lock_document`. Callers must acquire
    this lock before reading or mutating `asset.deleted_at`, so a concurrent update
    and soft-delete on the same asset can't both read the same stale state and both
    succeed."""
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        await session.execute(select(Asset.id).where(Asset.id == asset.id).with_for_update())
    await session.refresh(asset)


async def _lock_live_asset(
    session: AsyncSession, *, organisation_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    """Serialize schedule and event writes against an asset's soft deletion."""
    asset = await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    await _lock_asset(session, asset)
    if asset.deleted_at is not None:
        raise AssetNotFoundError(f"No asset {asset_id} in this organisation")
    return asset


async def create_asset(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_tag: str,
    name: str,
    asset_type: AssetType,
    serial_number: str | None,
    location: str | None,
    owner_id: uuid.UUID | None,
    status: AssetStatus,
    purchase_date: datetime.date | None,
    created_by_id: uuid.UUID,
) -> Asset:
    await _validate_owner(session, organisation_id=organisation_id, owner_id=owner_id)
    await _assert_asset_tag_available(
        session, organisation_id=organisation_id, asset_tag=asset_tag, exclude_asset_id=None
    )

    asset = Asset(
        organisation_id=organisation_id,
        asset_tag=asset_tag,
        name=name,
        asset_type=asset_type,
        serial_number=serial_number,
        location=location,
        owner_id=owner_id,
        status=status,
        purchase_date=purchase_date,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(asset)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Belt-and-braces alongside the check above: two concurrent creates for the
        # same asset_tag can both pass _assert_asset_tag_available before either
        # commits. The uq_assets_org_asset_tag constraint catches it; map that to
        # the same clean conflict the normal check-path raises, not a raw 500.
        await session.rollback()
        raise AssetTagConflictError(
            f"An asset with tag {asset_tag!r} already exists in this organisation"
        ) from exc
    await session.refresh(asset)
    return asset


async def get_asset(
    session: AsyncSession, *, organisation_id: uuid.UUID, asset_id: uuid.UUID
) -> Asset:
    asset = (
        await session.execute(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.organisation_id == organisation_id,
                Asset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise AssetNotFoundError(f"No asset {asset_id} in this organisation")
    return asset


async def list_assets(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_type: AssetType | None,
    status: AssetStatus | None,
    location: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Asset], int]:
    """List assets, optionally filtered by exact `asset_type`/`status`/`location`,
    and a case-insensitive substring `search` across `asset_tag`/`name`/
    `serial_number`."""
    filters = [Asset.organisation_id == organisation_id, Asset.deleted_at.is_(None)]
    if asset_type is not None:
        filters.append(Asset.asset_type == asset_type)
    if status is not None:
        filters.append(Asset.status == status)
    if location is not None:
        filters.append(Asset.location == location)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Asset.asset_tag.ilike(pattern),
                Asset.name.ilike(pattern),
                Asset.serial_number.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(Asset).where(*filters))
    ).scalar_one()
    result = await session.execute(
        select(Asset).where(*filters).order_by(Asset.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_asset(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    updated_by_id: uuid.UUID,
    asset_tag: str,
    name: str,
    asset_type: AssetType,
    serial_number: str | None,
    location: str | None,
    owner_id: uuid.UUID | None,
    status: AssetStatus,
    purchase_date: datetime.date | None,
) -> Asset:
    asset = await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    await _lock_asset(session, asset)
    if asset.deleted_at is not None:
        # get_asset's own deleted_at.is_(None) filter ran before this lock was
        # acquired; a concurrent delete could have committed in the window between
        # that read and this lock. Re-check post-lock so an update can never land on
        # an asset that is now soft-deleted -- the same class of gap an independent
        # review found (and this milestone's plan explicitly flags as worth guarding
        # proactively) in NCR's update_ncr.
        raise AssetNotFoundError(f"No asset {asset_id} in this organisation")
    await _validate_owner(session, organisation_id=organisation_id, owner_id=owner_id)
    await _assert_asset_tag_available(
        session, organisation_id=organisation_id, asset_tag=asset_tag, exclude_asset_id=asset_id
    )

    asset.asset_tag = asset_tag
    asset.name = name
    asset.asset_type = asset_type
    asset.serial_number = serial_number
    asset.location = location
    asset.owner_id = owner_id
    asset.status = status
    asset.purchase_date = purchase_date
    asset.updated_by_id = updated_by_id
    try:
        await session.commit()
    except IntegrityError as exc:
        # Same race as create_asset's belt-and-braces catch above.
        await session.rollback()
        raise AssetTagConflictError(
            f"An asset with tag {asset_tag!r} already exists in this organisation"
        ) from exc
    await session.refresh(asset)
    return asset


async def delete_asset(
    session: AsyncSession, *, organisation_id: uuid.UUID, asset_id: uuid.UUID
) -> None:
    """Soft delete (`deleted_at`) -- design decision 9: an asset carries
    audit-significant calibration history, matching `documents`/`ncrs`' precedent,
    unlike Products/Suppliers' hard-deletable pure reference data."""
    asset = await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    await _lock_asset(session, asset)
    asset.deleted_at = datetime.datetime.now(datetime.UTC)
    await session.commit()


# --- Calibration schedules -----------------------------------------------------


def _add_months(base_date: datetime.date, months: int) -> datetime.date:
    """Add `months` calendar months to `base_date`, clamping the day-of-month to
    the target month's last valid day (e.g. 31 Jan + 1 month = 28/29 Feb)."""
    total_months = base_date.month - 1 + months
    year = base_date.year + total_months // 12
    month = total_months % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return base_date.replace(year=year, month=month, day=day)


def _add_interval(
    base_date: datetime.date, value: int, unit: CalibrationIntervalUnit
) -> datetime.date:
    """Compute `base_date + value` in the given `unit` -- plan design decision 4:
    `next_due_date` is always server-computed from the asset's own
    operator-configured interval, never a hard-coded formula."""
    if unit == CalibrationIntervalUnit.DAYS:
        return base_date + datetime.timedelta(days=value)
    if unit == CalibrationIntervalUnit.MONTHS:
        return _add_months(base_date, value)
    return _add_months(base_date, value * 12)


async def _lock_schedule(session: AsyncSession, schedule: CalibrationSchedule) -> None:
    """Lock `schedule`'s row with `SELECT ... FOR UPDATE` (a no-op on SQLite), then
    refresh -- mirrors `_lock_asset`. Callers must acquire this before recomputing
    `next_due_date`, so two concurrent calibration events for the same asset (or a
    concurrent manual schedule update) can't both read the same stale interval and
    both commit an inconsistent `next_due_date`."""
    bind = session.bind
    if bind is not None and bind.dialect.name != "sqlite":
        await session.execute(
            select(CalibrationSchedule.id)
            .where(CalibrationSchedule.id == schedule.id)
            .with_for_update()
        )
    await session.refresh(schedule)


async def create_schedule(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    interval_value: int,
    interval_unit: CalibrationIntervalUnit,
    created_by_id: uuid.UUID,
) -> CalibrationSchedule:
    """Create-once: `POST` fails with `CalibrationScheduleAlreadyExistsError` if the
    asset already has a schedule -- use `update_schedule` (`PATCH`) to change one."""
    await _lock_live_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    existing = (
        await session.execute(
            select(CalibrationSchedule).where(CalibrationSchedule.asset_id == asset_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise CalibrationScheduleAlreadyExistsError(
            f"Asset {asset_id} already has a calibration schedule"
        )

    schedule = CalibrationSchedule(
        asset_id=asset_id,
        interval_value=interval_value,
        interval_unit=interval_unit,
        next_due_date=None,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(schedule)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Belt-and-braces alongside the check above: two concurrent creates for the
        # same asset can both pass the check before either commits. The
        # uq_calibration_schedules_asset_id constraint catches it; map that to the
        # same clean conflict the normal check-path raises, not a raw 500.
        await session.rollback()
        raise CalibrationScheduleAlreadyExistsError(
            f"Asset {asset_id} already has a calibration schedule"
        ) from exc
    await session.refresh(schedule)
    return schedule


async def get_schedule(
    session: AsyncSession, *, organisation_id: uuid.UUID, asset_id: uuid.UUID
) -> CalibrationSchedule:
    await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    schedule = (
        await session.execute(
            select(CalibrationSchedule).where(CalibrationSchedule.asset_id == asset_id)
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise CalibrationScheduleNotFoundError(f"Asset {asset_id} has no calibration schedule")
    return schedule


async def update_schedule(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    updated_by_id: uuid.UUID,
    interval_value: int,
    interval_unit: CalibrationIntervalUnit,
    next_due_date: datetime.date | None,
) -> CalibrationSchedule:
    await _lock_live_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    schedule = await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)
    await _lock_schedule(session, schedule)

    schedule.interval_value = interval_value
    schedule.interval_unit = interval_unit
    if next_due_date is not None:
        schedule.next_due_date = next_due_date
    schedule.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(schedule)
    return schedule


# --- Calibration events ----------------------------------------------------------


async def create_event(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    performed_at: datetime.date,
    performed_by_id: uuid.UUID | None,
    performed_by_supplier_id: uuid.UUID | None,
    certificate_document_id: uuid.UUID | None,
    result: CalibrationResult,
    notes: str | None,
    created_by_id: uuid.UUID,
) -> CalibrationEvent:
    """Record a calibration event and recompute the parent schedule's
    `next_due_date` in the same transaction (plan design decision 4), row-locking
    the schedule first so two concurrent events for the same asset can't both
    compute from the same stale `next_due_date`."""
    await _lock_live_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    schedule = await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)
    await _lock_schedule(session, schedule)

    if performed_by_id is not None:
        try:
            await get_person(session, organisation_id=organisation_id, person_id=performed_by_id)
        except PersonNotFoundError as exc:
            raise CalibrationEventPerformerNotFoundError(str(exc)) from exc
    if performed_by_supplier_id is not None:
        try:
            await get_supplier(
                session, organisation_id=organisation_id, supplier_id=performed_by_supplier_id
            )
        except SupplierNotFoundError as exc:
            raise CalibrationEventSupplierNotFoundError(str(exc)) from exc
    if certificate_document_id is not None:
        try:
            await get_document(
                session, organisation_id=organisation_id, document_id=certificate_document_id
            )
        except DocumentNotFoundError as exc:
            raise CalibrationEventDocumentNotFoundError(str(exc)) from exc

    latest_performed_at = (
        await session.execute(
            select(func.max(CalibrationEvent.performed_at)).where(
                CalibrationEvent.asset_id == asset_id
            )
        )
    ).scalar_one()
    computed_next_due_date = _add_interval(
        performed_at, schedule.interval_value, schedule.interval_unit
    )

    event = CalibrationEvent(
        asset_id=asset_id,
        performed_at=performed_at,
        performed_by_id=performed_by_id,
        performed_by_supplier_id=performed_by_supplier_id,
        certificate_document_id=certificate_document_id,
        result=result,
        next_due_date=computed_next_due_date,
        notes=notes,
        created_by_id=created_by_id,
    )
    session.add(event)
    if latest_performed_at is None or performed_at >= latest_performed_at:
        schedule.next_due_date = computed_next_due_date
    await session.commit()
    await session.refresh(event)
    return event


async def list_events(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[CalibrationEvent], int]:
    """Newest-first (by `performed_at`, the calibration date itself, not
    `created_at`) -- matching `supplier_performance_records`' newest-first history
    precedent, but ordered by the semantically meaningful date for equipment
    history rather than entry time."""
    await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(CalibrationEvent)
            .where(CalibrationEvent.asset_id == asset_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(CalibrationEvent)
        .where(CalibrationEvent.asset_id == asset_id)
        .order_by(CalibrationEvent.performed_at.desc(), CalibrationEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total
