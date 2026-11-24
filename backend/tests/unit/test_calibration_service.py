"""Unit tests for app/modules/calibration/service.py (SQLite, ORM-level only).

Per docs/modules/CalibrationAndAssetManagement.md and the Milestone 5 plan
(.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md#1-schema):
organisation-scoped CRUD for assets, the `asset_tag` uniqueness `409`, `owner_id`
validated against the People module's own service (never its model directly),
cross-organisation lookups raising a not-found error, and soft delete.
"""

import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

if TYPE_CHECKING:
    # Deferred at runtime (like every other calibration.models import in this file)
    # so that merely collecting this test module doesn't register calibration's
    # tables -- with their FKs to documents/suppliers/people -- on Base.metadata
    # before those modules are themselves imported, which breaks unrelated files'
    # bare `Base.metadata.create_all()` fixtures elsewhere in the suite.
    from app.modules.calibration.models import CalibrationIntervalUnit

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.calibration.models  # noqa: F401
    import app.modules.documents.models  # noqa: F401
    import app.modules.people.models  # noqa: F401
    import app.modules.suppliers.models  # noqa: F401
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


async def _create_supplier(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import create_supplier

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Calibration House",
            type=CompanyType.SUPPLIER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )
        supplier = await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=company.id,
            approval_status=ApprovalStatus.APPROVED,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )
        return supplier.id


@pytest.fixture
async def supplier_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_supplier(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_supplier_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_supplier(session_maker, organisation_id=other_organisation_id)


async def _create_document(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Calibration certificate",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        return document.id


@pytest.fixture
async def document_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_document(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_document_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_document(session_maker, organisation_id=other_organisation_id)


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


# --- Calibration schedules -----------------------------------------------------


async def test_create_and_get_schedule(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import create_schedule, get_schedule

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    async with session_maker() as session:
        schedule = await create_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=6,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            created_by_id=user_id,
        )

    assert schedule.interval_value == 6
    assert schedule.next_due_date is None

    async with session_maker() as session:
        fetched = await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)
    assert fetched.id == schedule.id


async def test_create_schedule_rejects_a_second_schedule_for_the_same_asset(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import (
        CalibrationScheduleAlreadyExistsError,
        create_schedule,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    async with session_maker() as session:
        await create_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=6,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        with pytest.raises(CalibrationScheduleAlreadyExistsError):
            await create_schedule(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                interval_value=1,
                interval_unit=CalibrationIntervalUnit.YEARS,
                created_by_id=user_id,
            )


async def test_schedule_request_rejects_non_positive_interval() -> None:
    from pydantic import ValidationError

    from app.modules.calibration.schemas import CalibrationScheduleCreateRequest

    with pytest.raises(ValidationError):
        CalibrationScheduleCreateRequest(interval_value=0, interval_unit="months")


async def test_get_schedule_raises_not_found_when_none_exists(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.calibration.service import CalibrationScheduleNotFoundError, get_schedule

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(CalibrationScheduleNotFoundError):
            await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)


async def test_get_schedule_raises_not_found_for_cross_organisation_asset(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.calibration.service import AssetNotFoundError, get_schedule

    asset_id = await _create_asset(
        session_maker, organisation_id=other_organisation_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)


async def test_update_schedule_changes_interval_and_manual_next_due_date(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import create_schedule, update_schedule

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    async with session_maker() as session:
        await create_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=6,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        updated = await update_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            updated_by_id=user_id,
            interval_value=1,
            interval_unit=CalibrationIntervalUnit.YEARS,
            next_due_date=datetime.date(2027, 1, 1),
        )

    assert updated.interval_value == 1
    assert updated.interval_unit == CalibrationIntervalUnit.YEARS
    assert updated.next_due_date == datetime.date(2027, 1, 1)


# --- Calibration events ----------------------------------------------------------


async def _create_schedule(
    session_maker: SessionMaker,
    *,
    organisation_id: uuid.UUID,
    asset_id: uuid.UUID,
    user_id: uuid.UUID,
    interval_value: int = 6,
    interval_unit: "CalibrationIntervalUnit | None" = None,
) -> None:
    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import create_schedule

    async with session_maker() as session:
        await create_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=interval_value,
            interval_unit=interval_unit or CalibrationIntervalUnit.MONTHS,
            created_by_id=user_id,
        )


async def test_create_event_computes_next_due_date_from_the_schedule_interval(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationIntervalUnit, CalibrationResult
    from app.modules.calibration.service import create_event, get_schedule

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker,
        organisation_id=organisation_id,
        asset_id=asset_id,
        user_id=user_id,
        interval_value=6,
        interval_unit=CalibrationIntervalUnit.MONTHS,
    )

    async with session_maker() as session:
        event = await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 8, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes=None,
            created_by_id=user_id,
        )

    assert event.next_due_date == datetime.date(2027, 2, 1)

    async with session_maker() as session:
        schedule = await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)
    assert schedule.next_due_date == datetime.date(2027, 2, 1)


async def test_create_event_clamps_month_end_day_correctly(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """31 Jan + 1 month must clamp to the last valid day of February, per
    _add_months -- a real interval-arithmetic edge case, not a contrived one
    (many calibration intervals are monthly)."""
    import datetime

    from app.modules.calibration.models import CalibrationIntervalUnit, CalibrationResult
    from app.modules.calibration.service import create_event

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker,
        organisation_id=organisation_id,
        asset_id=asset_id,
        user_id=user_id,
        interval_value=1,
        interval_unit=CalibrationIntervalUnit.MONTHS,
    )

    async with session_maker() as session:
        event = await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2027, 1, 31),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes=None,
            created_by_id=user_id,
        )

    assert event.next_due_date == datetime.date(2027, 2, 28)


async def test_create_event_rejects_without_an_existing_schedule(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import CalibrationScheduleNotFoundError, create_event

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(CalibrationScheduleNotFoundError):
            await create_event(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                performed_at=datetime.date(2026, 8, 1),
                performed_by_id=None,
                performed_by_supplier_id=None,
                certificate_document_id=None,
                result=CalibrationResult.PASS,
                notes=None,
                created_by_id=user_id,
            )


async def test_create_event_validates_performer_in_same_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_org_owner_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import (
        CalibrationEventPerformerNotFoundError,
        create_event,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(CalibrationEventPerformerNotFoundError):
            await create_event(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                performed_at=datetime.date(2026, 8, 1),
                performed_by_id=other_org_owner_id,
                performed_by_supplier_id=None,
                certificate_document_id=None,
                result=CalibrationResult.PASS,
                notes=None,
                created_by_id=user_id,
            )


async def test_create_event_validates_supplier_in_same_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_org_supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import (
        CalibrationEventSupplierNotFoundError,
        create_event,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(CalibrationEventSupplierNotFoundError):
            await create_event(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                performed_at=datetime.date(2026, 8, 1),
                performed_by_id=None,
                performed_by_supplier_id=other_org_supplier_id,
                certificate_document_id=None,
                result=CalibrationResult.PASS,
                notes=None,
                created_by_id=user_id,
            )


async def test_create_event_validates_certificate_document_in_same_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_org_document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import (
        CalibrationEventDocumentNotFoundError,
        create_event,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(CalibrationEventDocumentNotFoundError):
            await create_event(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                performed_at=datetime.date(2026, 8, 1),
                performed_by_id=None,
                performed_by_supplier_id=None,
                certificate_document_id=other_org_document_id,
                result=CalibrationResult.PASS,
                notes=None,
                created_by_id=user_id,
            )


async def test_list_events_returns_newest_first_and_scopes_to_the_asset(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import create_event, list_events

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )

    async with session_maker() as session:
        await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 1, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes="First",
            created_by_id=user_id,
        )
    async with session_maker() as session:
        await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 7, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.FAIL,
            notes="Second",
            created_by_id=user_id,
        )

    async with session_maker() as session:
        events, total = await list_events(
            session, organisation_id=organisation_id, asset_id=asset_id, limit=50, offset=0
        )

    assert total == 2
    assert events[0].notes == "Second"
    assert events[1].notes == "First"


async def test_create_event_locks_the_schedule_before_recomputing_next_due_date(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_lock_schedule` must run (and refresh the in-memory `schedule` object)
    before `create_event` reads `schedule.interval_value`/`interval_unit` to
    compute `next_due_date`, or a concurrent `update_schedule` that changes the
    interval and commits in the window between the initial fetch and the lock
    would be silently ignored. Simulate that race deterministically (matching
    `test_create_asset_maps_integrity_error_to_conflict_when_the_check_is_raced`'s
    pattern) by monkeypatching `_lock_schedule` to commit an interval change from
    a second session immediately before delegating to the real lock-and-refresh."""
    import datetime

    import app.modules.calibration.service as calibration_service
    from app.modules.calibration.models import CalibrationIntervalUnit, CalibrationResult
    from app.modules.calibration.service import _lock_schedule, create_event

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker,
        organisation_id=organisation_id,
        asset_id=asset_id,
        user_id=user_id,
        interval_value=6,
        interval_unit=CalibrationIntervalUnit.MONTHS,
    )

    original_lock_schedule = _lock_schedule

    async def _concurrently_change_interval_then_lock(session: object, schedule: object) -> None:
        async with session_maker() as other_session:
            from sqlalchemy import select

            from app.modules.calibration.models import CalibrationSchedule

            other_schedule = (
                await other_session.execute(
                    select(CalibrationSchedule).where(CalibrationSchedule.asset_id == asset_id)
                )
            ).scalar_one()
            other_schedule.interval_value = 1
            other_schedule.interval_unit = CalibrationIntervalUnit.YEARS
            await other_session.commit()
        await original_lock_schedule(session, schedule)  # type: ignore[arg-type]

    monkeypatch.setattr(
        calibration_service, "_lock_schedule", _concurrently_change_interval_then_lock
    )

    async with session_maker() as session:
        event = await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 1, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes=None,
            created_by_id=user_id,
        )

    # Must reflect the concurrently-committed 1-year interval (2027-01-01), not
    # the stale 6-month interval read before the lock (which would give 2026-07-01).
    assert event.next_due_date == datetime.date(2027, 1, 1)


async def test_create_event_rejects_asset_deleted_between_fetch_and_lock(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import datetime

    from sqlalchemy import select

    import app.modules.calibration.service as calibration_service
    from app.modules.calibration.models import Asset, CalibrationResult
    from app.modules.calibration.service import AssetNotFoundError, _lock_asset, create_event

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )
    original_lock = _lock_asset

    async def delete_before_lock(session: object, asset: object) -> None:
        async with session_maker() as other_session:
            other_asset = (
                await other_session.execute(select(Asset).where(Asset.id == asset_id))
            ).scalar_one()
            other_asset.deleted_at = datetime.datetime.now(datetime.UTC)
            await other_session.commit()
        await original_lock(session, asset)  # type: ignore[arg-type]

    monkeypatch.setattr(calibration_service, "_lock_asset", delete_before_lock)
    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await create_event(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                performed_at=datetime.date(2026, 8, 1),
                performed_by_id=None,
                performed_by_supplier_id=None,
                certificate_document_id=None,
                result=CalibrationResult.PASS,
                notes=None,
                created_by_id=user_id,
            )


async def test_backfilled_event_preserves_current_due_date_from_later_calibration(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationResult
    from app.modules.calibration.service import create_event, get_schedule

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    await _create_schedule(
        session_maker, organisation_id=organisation_id, asset_id=asset_id, user_id=user_id
    )
    async with session_maker() as session:
        await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 8, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        older = await create_event(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            performed_at=datetime.date(2026, 1, 1),
            performed_by_id=None,
            performed_by_supplier_id=None,
            certificate_document_id=None,
            result=CalibrationResult.PASS,
            notes="Historical backfill",
            created_by_id=user_id,
        )
    async with session_maker() as session:
        schedule = await get_schedule(session, organisation_id=organisation_id, asset_id=asset_id)
    assert older.next_due_date == datetime.date(2026, 7, 1)
    assert schedule.next_due_date == datetime.date(2027, 2, 1)


async def test_maintenance_schedule_create_get_update_and_live_asset_guard(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import (
        AssetMaintenanceScheduleAlreadyExistsError,
        create_maintenance_schedule,
        get_maintenance_schedule,
        update_maintenance_schedule,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    async with session_maker() as session:
        empty = await get_maintenance_schedule(
            session, organisation_id=organisation_id, asset_id=asset_id
        )
    assert empty is None
    async with session_maker() as session:
        row = await create_maintenance_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=3,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            next_due_date=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        with pytest.raises(AssetMaintenanceScheduleAlreadyExistsError):
            await create_maintenance_schedule(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                interval_value=1,
                interval_unit=CalibrationIntervalUnit.YEARS,
                next_due_date=None,
                created_by_id=user_id,
            )
    async with session_maker() as session:
        updated = await update_maintenance_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=6,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            next_due_date=datetime.date(2027, 1, 1),
            next_due_date_supplied=True,
            updated_by_id=user_id,
        )
    assert row.id == updated.id and updated.interval_value == 6
    assert updated.next_due_date == datetime.date(2027, 1, 1)


async def test_maintenance_partial_update_preserves_omitted_fields(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    import datetime

    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import (
        create_maintenance_schedule,
        update_maintenance_schedule,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    due = datetime.date(2027, 5, 1)
    async with session_maker() as session:
        await create_maintenance_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            interval_value=4,
            interval_unit=CalibrationIntervalUnit.MONTHS,
            next_due_date=due,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        row = await update_maintenance_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            updated_by_id=user_id,
            interval_value=5,
        )
        assert row.interval_unit == CalibrationIntervalUnit.MONTHS
        assert row.next_due_date == due
    async with session_maker() as session:
        cleared = await update_maintenance_schedule(
            session,
            organisation_id=organisation_id,
            asset_id=asset_id,
            updated_by_id=user_id,
            next_due_date=None,
            next_due_date_supplied=True,
        )
        assert cleared.next_due_date is None
        assert cleared.interval_value == 5


async def test_maintenance_model_declares_positive_interval_constraint() -> None:
    from typing import cast

    from sqlalchemy import CheckConstraint, Enum, Table

    from app.modules.calibration.models import AssetMaintenanceSchedule

    table = cast(Table, AssetMaintenanceSchedule.__table__)
    assert cast(Enum, table.c.interval_unit.type).name == "calibration_interval_unit"
    checks = [
        constraint for constraint in table.constraints if isinstance(constraint, CheckConstraint)
    ]
    assert any(
        constraint.name == "ck_asset_maintenance_schedules_positive_interval"
        and str(constraint.sqltext) == "interval_value > 0"
        for constraint in checks
    )


@pytest.mark.parametrize(
    "constraint_name,conflict,via_cause",
    [
        ("uq_asset_maintenance_schedules_asset_id", True, False),
        ("fk_asset_maintenance_schedules_created_by_id", False, False),
        ("uq_asset_maintenance_schedules_asset_id", True, True),
    ],
)
async def test_maintenance_create_classifies_only_unique_integrity_error(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
    constraint_name: str,
    conflict: bool,
    via_cause: bool,
) -> None:
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import (
        AssetMaintenanceScheduleAlreadyExistsError,
        create_maintenance_schedule,
    )

    class SimulatedWrapperError(Exception):
        diag: SimpleNamespace

    class SimulatedDriverError(Exception):
        constraint_name: str

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    async with session_maker() as session:

        async def fail_commit() -> None:
            original = SimulatedWrapperError("simulated")
            if via_cause:
                cause = SimulatedDriverError("driver unique violation")
                cause.constraint_name = constraint_name
                original.__cause__ = cause
            else:
                original.diag = SimpleNamespace(constraint_name=constraint_name)
            raise IntegrityError("INSERT", {}, original)

        monkeypatch.setattr(session, "commit", fail_commit)
        expected = AssetMaintenanceScheduleAlreadyExistsError if conflict else IntegrityError
        with pytest.raises(expected):
            await create_maintenance_schedule(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                interval_value=2,
                interval_unit=CalibrationIntervalUnit.MONTHS,
                next_due_date=None,
                created_by_id=user_id,
            )


async def test_calibration_due_window_is_scoped_and_defaults_when_invalid(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
) -> None:
    from sqlalchemy import select

    from app.models.configuration import Configuration
    from app.modules.calibration.reminder_config import (
        REMINDER_WINDOW_KEY,
        get_reminder_window_days,
    )

    async with session_maker() as session:
        assert await get_reminder_window_days(session, organisation_id=organisation_id) == 30
        session.add(
            Configuration(
                organisation_id=organisation_id, key=REMINDER_WINDOW_KEY, value={"days": 7}
            )
        )
        session.add(
            Configuration(
                organisation_id=other_organisation_id,
                key=REMINDER_WINDOW_KEY,
                value={"days": 45},
            )
        )
        await session.commit()
    async with session_maker() as session:
        assert await get_reminder_window_days(session, organisation_id=organisation_id) == 7
        assert await get_reminder_window_days(session, organisation_id=other_organisation_id) == 45
        config = (
            await session.execute(
                select(Configuration).where(Configuration.organisation_id == organisation_id)
            )
        ).scalar_one()
        config.value = {"days": -1}
        await session.commit()
    async with session_maker() as session:
        assert await get_reminder_window_days(session, organisation_id=organisation_id) == 30


async def test_maintenance_schedule_service_rejects_foreign_and_deleted_assets(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.calibration.models import CalibrationIntervalUnit
    from app.modules.calibration.service import (
        AssetNotFoundError,
        create_maintenance_schedule,
        delete_asset,
        get_maintenance_schedule,
        update_maintenance_schedule,
    )

    asset_id = await _create_asset(session_maker, organisation_id=organisation_id, user_id=user_id)
    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await create_maintenance_schedule(
                session,
                organisation_id=other_organisation_id,
                asset_id=asset_id,
                interval_value=1,
                interval_unit=CalibrationIntervalUnit.YEARS,
                next_due_date=None,
                created_by_id=user_id,
            )
    async with session_maker() as session:
        await delete_asset(session, organisation_id=organisation_id, asset_id=asset_id)
    async with session_maker() as session:
        with pytest.raises(AssetNotFoundError):
            await get_maintenance_schedule(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
            )
        with pytest.raises(AssetNotFoundError):
            await update_maintenance_schedule(
                session,
                organisation_id=organisation_id,
                asset_id=asset_id,
                updated_by_id=user_id,
                interval_value=2,
            )
