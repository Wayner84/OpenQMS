"""Business logic for the Calibration and Asset Management module. Per
docs/modules/CalibrationAndAssetManagement.md and the Milestone 5 plan
(.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md): every
operation is scoped to the caller's organisation; `owner_id` is validated against
the People module's own service layer (module boundary rule -- see
docs/CodingStandards.md#backend-python), never queried directly.
"""

import datetime
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calibration.models import Asset, AssetStatus, AssetType
from app.modules.people.service import PersonNotFoundError, get_person


class AssetNotFoundError(Exception):
    """Raised when an asset id doesn't exist (or is soft-deleted) in the caller's
    organisation."""


class AssetTagConflictError(Exception):
    """Raised when creating/updating an asset with an `asset_tag` already used by
    another asset in the same organisation."""


class AssetOwnerNotFoundError(Exception):
    """Raised when an asset's `owner_id` doesn't exist in the caller's organisation."""


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
