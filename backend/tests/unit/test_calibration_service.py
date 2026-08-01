"""Unit tests for app/modules/calibration/service.py (SQLite, ORM-level only).

Per docs/modules/CalibrationAndAssetManagement.md and the Milestone 5 plan
(.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md#1-schema):
organisation-scoped CRUD for assets, the `asset_tag` uniqueness `409`, `owner_id`
validated against the People module's own service (never its model directly),
cross-organisation lookups raising a not-found error, and soft delete.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.calibration.models  # noqa: F401
    import app.modules.people.models  # noqa: F401
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


@pytest.fixture
async def other_organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Other Organisation", slug="other")
        session.add(org)
        await session.commit()
        return org.id


@pytest.fixture
async def user_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.models.user import User

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="creator@example.com",
            hashed_password="irrelevant",
            full_name="Creator",
        )
        session.add(user)
        await session.commit()
        return user.id


async def _create_person(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.people.service import create_person

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Olive",
            last_name="Owner",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )
        return person.id


@pytest.fixture
async def owner_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_person(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_owner_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_person(session_maker, organisation_id=other_organisation_id)


async def _create_asset(
    session_maker: SessionMaker,
    *,
    organisation_id: uuid.UUID,
    asset_tag: str = "CAL-001",
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import create_asset

    async with session_maker() as session:
        asset = await create_asset(
            session,
            organisation_id=organisation_id,
            asset_tag=asset_tag,
            name="Digital caliper",
            asset_type=AssetType.MEASURING_EQUIPMENT,
            serial_number=None,
            location=None,
            owner_id=None,
            status=AssetStatus.IN_SERVICE,
            purchase_date=None,
            created_by_id=user_id if user_id is not None else uuid.uuid4(),
        )
        return asset.id


async def test_create_asset_sets_default_status_and_attribution(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import create_asset

    async with session_maker() as session:
        asset = await create_asset(
            session,
            organisation_id=organisation_id,
            asset_tag="CAL-100",
            name="Height gauge",
            asset_type=AssetType.INSPECTION_EQUIPMENT,
            serial_number="SN-1",
            location="Metrology lab",
            owner_id=None,
            status=AssetStatus.IN_SERVICE,
            purchase_date=None,
            created_by_id=user_id,
        )

    assert asset.status == AssetStatus.IN_SERVICE
    assert asset.created_by_id == user_id
    assert asset.updated_by_id == user_id


async def test_create_asset_rejects_duplicate_asset_tag_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import AssetTagConflictError, create_asset

    await _create_asset(session_maker, organisation_id=organisation_id, asset_tag="CAL-DUP")

    async with session_maker() as session:
        with pytest.raises(AssetTagConflictError):
            await create_asset(
                session,
                organisation_id=organisation_id,
                asset_tag="CAL-DUP",
                name="Another caliper",
                asset_type=AssetType.MEASURING_EQUIPMENT,
                serial_number=None,
                location=None,
                owner_id=None,
                status=AssetStatus.IN_SERVICE,
                purchase_date=None,
                created_by_id=user_id,
            )


async def test_create_asset_maps_integrity_error_to_conflict_when_the_check_is_raced(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same TOCTOU class as Products' `_assert_part_number_available` finding
    (Milestone 3 closeout): `_assert_asset_tag_available` is a check-then-insert
    with no row lock. Simulate the race deterministically by monkeypatching the
    check to a no-op, so the second create reaches `commit()` with a real
    duplicate already present."""
    import app.modules.calibration.service as calibration_service
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import AssetTagConflictError, create_asset

    await _create_asset(session_maker, organisation_id=organisation_id, asset_tag="CAL-RACE")

    async def _no_op_check(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(calibration_service, "_assert_asset_tag_available", _no_op_check)

    async with session_maker() as session:
        with pytest.raises(AssetTagConflictError):
            await create_asset(
                session,
                organisation_id=organisation_id,
                asset_tag="CAL-RACE",
                name="Another caliper",
                asset_type=AssetType.MEASURING_EQUIPMENT,
                serial_number=None,
                location=None,
                owner_id=None,
                status=AssetStatus.IN_SERVICE,
                purchase_date=None,
                created_by_id=user_id,
            )


async def test_create_asset_allows_same_asset_tag_in_different_organisations(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import create_asset

    await _create_asset(session_maker, organisation_id=organisation_id, asset_tag="CAL-SHARED")

    async with session_maker() as session:
        asset = await create_asset(
            session,
            organisation_id=other_organisation_id,
            asset_tag="CAL-SHARED",
            name="Also a caliper",
            asset_type=AssetType.MEASURING_EQUIPMENT,
            serial_number=None,
            location=None,
            owner_id=None,
            status=AssetStatus.IN_SERVICE,
            purchase_date=None,
            created_by_id=user_id,
        )

    assert asset.asset_tag == "CAL-SHARED"


async def test_create_asset_rejects_owner_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_org_owner_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import AssetOwnerNotFoundError, create_asset

    async with session_maker() as session:
        with pytest.raises(AssetOwnerNotFoundError):
            await create_asset(
                session,
                organisation_id=organisation_id,
                asset_tag="CAL-200",
                name="Torque wrench",
                asset_type=AssetType.MEASURING_EQUIPMENT,
                serial_number=None,
                location=None,
                owner_id=other_org_owner_id,
                status=AssetStatus.IN_SERVICE,
                purchase_date=None,
                created_by_id=user_id,
            )


async def test_get_asset_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.calibration.service import AssetNotFoundError, get_asset

    asset_id = await _create_asset(session_maker, organisation_id=other_organisation_id)

    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)


async def test_list_assets_filters_by_type_status_location_and_search(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import create_asset, list_assets

    async with session_maker() as session:
        await create_asset(
            session,
            organisation_id=organisation_id,
            asset_tag="CAL-A",
            name="Digital caliper",
            asset_type=AssetType.MEASURING_EQUIPMENT,
            serial_number=None,
            location="Lab A",
            owner_id=None,
            status=AssetStatus.IN_SERVICE,
            purchase_date=None,
            created_by_id=user_id,
        )
        await create_asset(
            session,
            organisation_id=organisation_id,
            asset_tag="CAL-B",
            name="Forklift",
            asset_type=AssetType.COMPANY_ASSET,
            serial_number=None,
            location="Warehouse",
            owner_id=None,
            status=AssetStatus.OUT_OF_SERVICE,
            purchase_date=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        by_type, by_type_total = await list_assets(
            session,
            organisation_id=organisation_id,
            asset_type=AssetType.COMPANY_ASSET,
            status=None,
            location=None,
            search=None,
            limit=50,
            offset=0,
        )
        by_status, by_status_total = await list_assets(
            session,
            organisation_id=organisation_id,
            asset_type=None,
            status=AssetStatus.OUT_OF_SERVICE,
            location=None,
            search=None,
            limit=50,
            offset=0,
        )
        by_location, by_location_total = await list_assets(
            session,
            organisation_id=organisation_id,
            asset_type=None,
            status=None,
            location="Lab A",
            search=None,
            limit=50,
            offset=0,
        )
        by_search, by_search_total = await list_assets(
            session,
            organisation_id=organisation_id,
            asset_type=None,
            status=None,
            location=None,
            search="caliper",
            limit=50,
            offset=0,
        )

    assert by_type_total == 1
    assert by_type[0].asset_tag == "CAL-B"
    assert by_status_total == 1
    assert by_status[0].asset_tag == "CAL-B"
    assert by_location_total == 1
    assert by_location[0].asset_tag == "CAL-A"
    assert by_search_total == 1
    assert by_search[0].asset_tag == "CAL-A"


async def test_list_assets_excludes_soft_deleted(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.service import delete_asset, list_assets

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    async with session_maker() as session:
        await delete_asset(session, organisation_id=organisation_id, asset_id=asset_id)

    async with session_maker() as session:
        assets, total = await list_assets(
            session,
            organisation_id=organisation_id,
            asset_type=None,
            status=None,
            location=None,
            search=None,
            limit=50,
            offset=0,
        )

    assert total == 0
    assert assets == []


async def test_update_asset_rejects_conflicting_asset_tag(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import AssetTagConflictError, update_asset

    await _create_asset(session_maker, organisation_id=organisation_id, asset_tag="CAL-A")
    asset_b_id = await _create_asset(
        session_maker, organisation_id=organisation_id, asset_tag="CAL-B"
    )

    async with session_maker() as session:
        with pytest.raises(AssetTagConflictError):
            await update_asset(
                session,
                organisation_id=organisation_id,
                asset_id=asset_b_id,
                updated_by_id=user_id,
                asset_tag="CAL-A",
                name="Digital caliper",
                asset_type=AssetType.MEASURING_EQUIPMENT,
                serial_number=None,
                location=None,
                owner_id=None,
                status=AssetStatus.IN_SERVICE,
                purchase_date=None,
            )


async def test_update_asset_allows_keeping_its_own_asset_tag(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import AssetStatus, AssetType
    from app.modules.calibration.service import update_asset

    asset_id = await _create_asset(
        session_maker, organisation_id=organisation_id, asset_tag="CAL-SELF"
    )

    async with session_maker() as session:
        updated = await update_asset(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            updated_by_id=user_id,
            asset_tag="CAL-SELF",
            name="Updated name",
            asset_type=AssetType.MEASURING_EQUIPMENT,
            serial_number="SN-2",
            location="Lab B",
            owner_id=None,
            status=AssetStatus.OUT_OF_SERVICE,
            purchase_date=None,
        )

    assert updated.name == "Updated name"
    assert updated.status == AssetStatus.OUT_OF_SERVICE
    assert updated.updated_by_id == user_id


async def test_update_asset_rejects_an_asset_deleted_after_the_initial_fetch(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proactive frozen-once-closed-style regression test (Milestone 5 plan design
    decision 9 / the standing checklist item added after Milestone 4's three
    reactive findings of this exact gap): `update_asset` must re-check
    `deleted_at` after acquiring the row lock, or a concurrent delete that commits
    in the window between `get_asset`'s read and the lock could be silently
    overwritten by a still-in-flight update. Same pattern as
    `test_update_ncr_rejects_an_ncr_deleted_after_the_initial_fetch`."""
    import datetime

    from sqlalchemy import select

    import app.modules.calibration.service as calibration_service
    from app.modules.calibration.models import Asset, AssetStatus, AssetType
    from app.modules.calibration.service import AssetNotFoundError, _lock_asset, update_asset

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    original_lock_asset = _lock_asset

    async def _concurrently_delete_then_lock(session: object, asset: object) -> None:
        # Bypasses delete_asset itself (which calls the now-patched module-level
        # _lock_asset and would recurse into this same function) -- writes
        # deleted_at directly instead, simulating a concurrent delete that commits
        # in the window between the caller's initial get_asset() fetch and this
        # lock being acquired.
        async with session_maker() as other_session:
            other_asset = (
                await other_session.execute(select(Asset).where(Asset.id == asset_id))
            ).scalar_one()
            other_asset.deleted_at = datetime.datetime.now(datetime.UTC)
            await other_session.commit()
        await original_lock_asset(session, asset)  # type: ignore[arg-type]

    monkeypatch.setattr(calibration_service, "_lock_asset", _concurrently_delete_then_lock)

    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await update_asset(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                updated_by_id=user_id,
                asset_tag="CAL-001",
                name="Should not apply",
                asset_type=AssetType.MEASURING_EQUIPMENT,
                serial_number=None,
                location=None,
                owner_id=None,
                status=AssetStatus.IN_SERVICE,
                purchase_date=None,
            )


async def test_delete_asset_soft_deletes_and_excludes_from_get(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.service import AssetNotFoundError, delete_asset, get_asset

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    async with session_maker() as session:
        await delete_asset(session, organisation_id=organisation_id, asset_id=asset_id)

    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await get_asset(session, organisation_id=organisation_id, asset_id=asset_id)
