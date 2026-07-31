"""Unit tests for app/modules/ncr/service.py (SQLite, ORM-level only).

Per docs/modules/NCR.md and the Milestone 4 plan
(.hermes/plans/2026-07-29-milestone-4-ncr.md#1-schema): organisation-scoped CRUD for
NCRs, `product_id`/`supplier_id`/`raised_by_id` validated against the Products/
Suppliers/People modules' own services (never their models directly), the
type/supplier_id invariant, cross-organisation lookups raising a not-found error,
soft delete, and the one-directional transition workflow (no skipping stages, no
moving backward once closed).
"""

import datetime
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.documents.models  # noqa: F401
    import app.modules.ncr.models  # noqa: F401
    import app.modules.people.models  # noqa: F401
    import app.modules.products.models  # noqa: F401
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
            first_name="Quinn",
            last_name="Reporter",
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
async def raised_by_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_person(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_person_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_person(session_maker, organisation_id=other_organisation_id)


async def _create_product(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.products.models import ProductType
    from app.modules.products.service import create_product

    async with session_maker() as session:
        product = await create_product(
            session,
            organisation_id=organisation_id,
            part_number="PN-001",
            description="A widget",
            revision="A",
            category_id=None,
            type=ProductType.INTERNAL,
            manufacturing_notes=None,
            created_by_id=None,
        )
        return product.id


@pytest.fixture
async def product_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_product(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_product_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_product(session_maker, organisation_id=other_organisation_id)


async def _create_supplier(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import create_supplier

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Supplies Ltd",
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
            title="Inspection photo",
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


async def _create_ncr(
    session_maker: SessionMaker,
    *,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
    **overrides: object,
) -> uuid.UUID:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import create_ncr

    kwargs: dict[str, object] = {
        "type": NcrType.INTERNAL,
        "product_id": None,
        "supplier_id": None,
        "raised_by_id": raised_by_id,
        "description": "A widget was out of spec",
        "root_cause_summary": None,
        "created_by_id": user_id,
    }
    kwargs.update(overrides)

    async with session_maker() as session:
        ncr = await create_ncr(session, organisation_id=organisation_id, **kwargs)  # type: ignore[arg-type]
        return ncr.id


# --- Create ------------------------------------------------------------------


async def test_ncrs_number_is_unique_per_organisation_at_the_database_level(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Independent review finding: `ncrs` had no DB-level uniqueness backstop on
    `number`, unlike every other server-generated-number table in this codebase
    (`documents.uq_documents_org_number`). The `SELECT ... FOR UPDATE` numbering
    lock should make a real duplicate unreachable through the service layer, but
    the constraint itself -- inserting two rows with the same
    (organisation_id, number) directly -- must still reject at the database."""
    from sqlalchemy.exc import IntegrityError

    from app.modules.ncr.models import Ncr, NcrStatus, NcrType

    async with session_maker() as session:
        session.add(
            Ncr(
                organisation_id=organisation_id,
                number="NCR-0001",
                type=NcrType.INTERNAL,
                status=NcrStatus.OPEN,
                raised_by_id=raised_by_id,
                description="First",
                created_by_id=user_id,
                updated_by_id=user_id,
            )
        )
        await session.commit()

        session.add(
            Ncr(
                organisation_id=organisation_id,
                number="NCR-0001",
                type=NcrType.INTERNAL,
                status=NcrStatus.OPEN,
                raised_by_id=raised_by_id,
                description="Duplicate number",
                created_by_id=user_id,
                updated_by_id=user_id,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_create_ncr_generates_sequential_internal_numbers(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import create_ncr

    async with session_maker() as session:
        first = await create_ncr(
            session,
            organisation_id=organisation_id,
            type=NcrType.INTERNAL,
            product_id=None,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="First issue",
            root_cause_summary=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        second = await create_ncr(
            session,
            organisation_id=organisation_id,
            type=NcrType.INTERNAL,
            product_id=None,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="Second issue",
            root_cause_summary=None,
            created_by_id=user_id,
        )

    assert first.number == "NCR-0001"
    assert second.number == "NCR-0002"
    assert first.status.value == "open"


async def test_create_ncr_uses_the_supplier_prefix_and_an_independent_sequence(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import create_ncr

    async with session_maker() as session:
        internal = await create_ncr(
            session,
            organisation_id=organisation_id,
            type=NcrType.INTERNAL,
            product_id=None,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="Internal issue",
            root_cause_summary=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        supplier_ncr = await create_ncr(
            session,
            organisation_id=organisation_id,
            type=NcrType.SUPPLIER,
            product_id=None,
            supplier_id=supplier_id,
            raised_by_id=raised_by_id,
            description="Supplier issue",
            root_cause_summary=None,
            created_by_id=user_id,
        )

    assert internal.number == "NCR-0001"
    assert supplier_ncr.number == "SNCR-0001"


async def test_create_ncr_records_the_initial_status_history_entry(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import list_status_history

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        entries, total = await list_status_history(
            session, organisation_id=organisation_id, ncr_id=ncr_id, limit=50, offset=0
        )

    assert total == 1
    assert entries[0].from_status is None
    assert entries[0].to_status.value == "open"
    assert entries[0].changed_by_id == user_id


async def test_create_ncr_rejects_product_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    other_org_product_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrProductNotFoundError

    with pytest.raises(NcrProductNotFoundError):
        await _create_ncr(
            session_maker,
            organisation_id=organisation_id,
            raised_by_id=raised_by_id,
            user_id=user_id,
            product_id=other_org_product_id,
        )


async def test_create_ncr_rejects_supplier_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    other_org_supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import NcrSupplierNotFoundError

    with pytest.raises(NcrSupplierNotFoundError):
        await _create_ncr(
            session_maker,
            organisation_id=organisation_id,
            raised_by_id=raised_by_id,
            user_id=user_id,
            type=NcrType.SUPPLIER,
            supplier_id=other_org_supplier_id,
        )


async def test_create_ncr_rejects_raised_by_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_org_person_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrRaisedByNotFoundError

    with pytest.raises(NcrRaisedByNotFoundError):
        await _create_ncr(
            session_maker,
            organisation_id=organisation_id,
            raised_by_id=other_org_person_id,
            user_id=user_id,
        )


# --- Get / list ----------------------------------------------------------------


async def test_get_ncr_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker,
    other_organisation_id: uuid.UUID,
    organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, get_ncr

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)


async def test_list_ncrs_filters_by_type_status_and_search(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import list_ncrs

    await _create_ncr(
        session_maker,
        organisation_id=organisation_id,
        raised_by_id=raised_by_id,
        user_id=user_id,
        description="Bracket bent out of spec",
    )
    await _create_ncr(
        session_maker,
        organisation_id=organisation_id,
        raised_by_id=raised_by_id,
        user_id=user_id,
        type=NcrType.SUPPLIER,
        supplier_id=supplier_id,
        description="Late delivery",
    )

    async with session_maker() as session:
        by_type, type_total = await list_ncrs(
            session,
            organisation_id=organisation_id,
            type=NcrType.SUPPLIER,
            status=None,
            product_id=None,
            supplier_id=None,
            raised_by_id=None,
            search=None,
            limit=50,
            offset=0,
        )
        by_search, search_total = await list_ncrs(
            session,
            organisation_id=organisation_id,
            type=None,
            status=None,
            product_id=None,
            supplier_id=None,
            raised_by_id=None,
            search="bracket",
            limit=50,
            offset=0,
        )

    assert type_total == 1
    assert by_type[0].type.value == "supplier"
    assert search_total == 1
    assert "Bracket" in by_search[0].description


# --- Update / delete -------------------------------------------------------------


async def test_update_ncr_changes_fields_and_validates_links(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    product_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import update_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        updated = await update_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            updated_by_id=user_id,
            type=NcrType.INTERNAL,
            product_id=product_id,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="Updated description",
            root_cause_summary="Tooling wear",
        )

    assert updated.product_id == product_id
    assert updated.description == "Updated description"
    assert updated.root_cause_summary == "Tooling wear"
    assert updated.updated_by_id == user_id


async def test_delete_ncr_soft_deletes_and_excludes_from_get(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, delete_ncr, get_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        await delete_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await get_ncr(session, organisation_id=organisation_id, ncr_id=ncr_id)


# --- Transition workflow ---------------------------------------------------------


async def test_transition_moves_through_the_full_sequence(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    sequence = [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
        NcrStatus.CLOSED,
    ]
    for to_status in sequence:
        async with session_maker() as session:
            ncr = await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )
        assert ncr.status == to_status

    assert ncr.closed_at is not None


async def test_transition_rejects_skipping_a_stage(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import InvalidNcrTransitionError, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(InvalidNcrTransitionError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.CONTAINMENT,
                changed_by_id=user_id,
                comments=None,
            )


async def test_transition_rejects_moving_backward(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import InvalidNcrTransitionError, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await transition_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            to_status=NcrStatus.INVESTIGATE,
            changed_by_id=user_id,
            comments=None,
        )

    async with session_maker() as session:
        with pytest.raises(InvalidNcrTransitionError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.OPEN,
                changed_by_id=user_id,
                comments=None,
            )


async def test_transition_rejects_once_already_closed(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import InvalidNcrTransitionError, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    for to_status in [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
        NcrStatus.CLOSED,
    ]:
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )

    async with session_maker() as session:
        with pytest.raises(InvalidNcrTransitionError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.CLOSED,
                changed_by_id=user_id,
                comments=None,
            )


async def test_transition_records_a_status_history_row_with_comments(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import list_status_history, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        await transition_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            to_status=NcrStatus.INVESTIGATE,
            changed_by_id=user_id,
            comments="Starting the investigation",
        )

    async with session_maker() as session:
        entries, total = await list_status_history(
            session, organisation_id=organisation_id, ncr_id=ncr_id, limit=50, offset=0
        )

    assert total == 2
    assert entries[1].from_status == NcrStatus.OPEN
    assert entries[1].to_status == NcrStatus.INVESTIGATE
    assert entries[1].comments == "Starting the investigation"


async def test_transition_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import NcrNotFoundError, transition_ncr

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.INVESTIGATE,
                changed_by_id=user_id,
                comments=None,
            )


# --- Soft-delete / transition race (independent security review finding) --------


async def test_transition_rejects_an_ncr_deleted_after_the_initial_fetch(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review finding: `get_ncr`'s `deleted_at.is_(None)` filter runs
    before `_lock_ncr` acquires the row lock, so a concurrent admin delete could
    commit in between -- without a post-lock re-check, the transition would proceed
    against a now-deleted NCR. Simulate that race deterministically (real
    concurrency can't be forced to interleave reliably in a test) by monkeypatching
    `_lock_ncr` to soft-delete the NCR, in a separate session, as a side effect of
    "acquiring the lock"."""
    import app.modules.ncr.service as ncr_service
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import NcrNotFoundError, _lock_ncr, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    original_lock_ncr = _lock_ncr

    async def _concurrently_delete_then_lock(session: object, ncr: object) -> None:
        # Simulates a concurrent delete that commits in the window between the
        # caller's initial get_ncr() fetch and this lock being acquired -- so it
        # must run and commit *before* original_lock_ncr's own
        # SELECT ... FOR UPDATE + refresh(), which is what should pick up the new
        # deleted_at (mirroring how a real second transaction would only observe
        # the first transaction's committed write once it acquires the row lock in
        # turn). Deliberately bypasses delete_ncr itself (which calls the
        # now-patched module-level _lock_ncr and would recurse into this same
        # function) -- writes deleted_at directly instead.
        async with session_maker() as other_session:
            from app.modules.ncr.models import Ncr

            other_ncr = (
                await other_session.execute(select(Ncr).where(Ncr.id == ncr_id))
            ).scalar_one()
            other_ncr.deleted_at = datetime.datetime.now(datetime.UTC)
            await other_session.commit()
        await original_lock_ncr(session, ncr)  # type: ignore[arg-type]

    monkeypatch.setattr(ncr_service, "_lock_ncr", _concurrently_delete_then_lock)

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.INVESTIGATE,
                changed_by_id=user_id,
                comments=None,
            )


async def test_update_ncr_rejects_an_ncr_deleted_after_the_initial_fetch(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same TOCTOU class as
    test_transition_rejects_an_ncr_deleted_after_the_initial_fetch, for
    `update_ncr`."""
    import app.modules.ncr.service as ncr_service
    from app.modules.ncr.models import NcrType
    from app.modules.ncr.service import NcrNotFoundError, _lock_ncr, update_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    original_lock_ncr = _lock_ncr

    async def _concurrently_delete_then_lock(session: object, ncr: object) -> None:
        # Simulates a concurrent delete that commits in the window between the
        # caller's initial get_ncr() fetch and this lock being acquired -- so it
        # must run and commit *before* original_lock_ncr's own
        # SELECT ... FOR UPDATE + refresh(), which is what should pick up the new
        # deleted_at (mirroring how a real second transaction would only observe
        # the first transaction's committed write once it acquires the row lock in
        # turn). Deliberately bypasses delete_ncr itself (which calls the
        # now-patched module-level _lock_ncr and would recurse into this same
        # function) -- writes deleted_at directly instead.
        async with session_maker() as other_session:
            from app.modules.ncr.models import Ncr

            other_ncr = (
                await other_session.execute(select(Ncr).where(Ncr.id == ncr_id))
            ).scalar_one()
            other_ncr.deleted_at = datetime.datetime.now(datetime.UTC)
            await other_session.commit()
        await original_lock_ncr(session, ncr)  # type: ignore[arg-type]

    monkeypatch.setattr(ncr_service, "_lock_ncr", _concurrently_delete_then_lock)

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await update_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                updated_by_id=user_id,
                type=NcrType.INTERNAL,
                product_id=None,
                supplier_id=None,
                raised_by_id=raised_by_id,
                description="Updated while a concurrent delete raced in",
                root_cause_summary=None,
            )


# --- Actions -------------------------------------------------------------------


async def test_create_action_defaults_to_open(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import create_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Retrain operator",
            owner_id=raised_by_id,
            due_date=None,
            created_by_id=user_id,
        )

    assert action.status == NcrActionStatus.OPEN
    assert action.completed_at is None
    assert action.owner_id == raised_by_id


async def test_create_action_locks_the_parent_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review finding: without locking the parent NCR row the same way
    transition_ncr's close guard does, a concurrent create_action and
    transition-to-closed could race -- the close guard's open-actions count could
    run and see zero before this insert commits. Assert the lock is actually taken
    (a spy on _lock_ncr), since SQLite (used by this unit-test suite) has no real
    row-level locking to prove the race is closed end-to-end -- that's covered by
    a real-concurrency integration test instead."""
    import app.modules.ncr.service as ncr_service
    from app.modules.ncr.service import create_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    locked_ncr_ids: list[uuid.UUID] = []
    original_lock_ncr = ncr_service._lock_ncr

    async def _spy_lock_ncr(session: object, ncr: object) -> None:
        locked_ncr_ids.append(ncr.id)  # type: ignore[attr-defined]
        await original_lock_ncr(session, ncr)  # type: ignore[arg-type]

    monkeypatch.setattr(ncr_service, "_lock_ncr", _spy_lock_ncr)

    async with session_maker() as session:
        await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    assert locked_ncr_ids == [ncr_id]


async def test_update_action_locks_the_parent_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same reasoning as test_create_action_locks_the_parent_ncr, for update_action
    (e.g. reopening an action concurrently with a close)."""
    import app.modules.ncr.service as ncr_service
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import create_action, update_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    locked_ncr_ids: list[uuid.UUID] = []
    original_lock_ncr = ncr_service._lock_ncr

    async def _spy_lock_ncr(session: object, ncr: object) -> None:
        locked_ncr_ids.append(ncr.id)  # type: ignore[attr-defined]
        await original_lock_ncr(session, ncr)  # type: ignore[arg-type]

    monkeypatch.setattr(ncr_service, "_lock_ncr", _spy_lock_ncr)

    async with session_maker() as session:
        await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.COMPLETE,
        )

    assert locked_ncr_ids == [ncr_id]


async def test_create_action_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, create_action

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await create_action(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                description="Should not be created",
                owner_id=None,
                due_date=None,
                created_by_id=user_id,
            )


async def test_create_action_rejects_owner_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    other_org_person_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrActionOwnerNotFoundError, create_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(NcrActionOwnerNotFoundError):
            await create_action(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                description="Should not be created",
                owner_id=other_org_person_id,
                due_date=None,
                created_by_id=user_id,
            )


async def test_list_actions_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, list_actions

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await list_actions(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                limit=50,
                offset=0,
            )


async def test_update_action_marks_complete_and_stamps_completed_at(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import create_action, update_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        updated = await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.COMPLETE,
        )

    assert updated.status == NcrActionStatus.COMPLETE
    assert updated.completed_at is not None


async def test_update_action_reopening_clears_completed_at(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import create_action, update_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.COMPLETE,
        )

    async with session_maker() as session:
        reopened = await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Retrain operator",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.OPEN,
        )

    assert reopened.status == NcrActionStatus.OPEN
    assert reopened.completed_at is None


async def test_update_action_raises_not_found_for_cross_organisation_action(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import NcrActionNotFoundError, create_action, update_action

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=other_organisation_id,
            ncr_id=other_ncr_id,
            description="Org B action",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        with pytest.raises(NcrActionNotFoundError):
            await update_action(
                session,
                organisation_id=organisation_id,
                action_id=action.id,
                description="Hijacked",
                owner_id=None,
                due_date=None,
                status=NcrActionStatus.OPEN,
            )


# --- Close-blocked-while-actions-open guard (design decision 4) -----------------


async def test_transition_to_closed_is_blocked_while_an_action_is_open(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import (
        NcrCloseBlockedByOpenActionsError,
        create_action,
        transition_ncr,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Still outstanding",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    for to_status in [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
    ]:
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )

    async with session_maker() as session:
        with pytest.raises(NcrCloseBlockedByOpenActionsError):
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=NcrStatus.CLOSED,
                changed_by_id=user_id,
                comments=None,
            )


async def test_transition_to_closed_succeeds_once_the_action_is_complete(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus, NcrStatus
    from app.modules.ncr.service import create_action, transition_ncr, update_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Will be completed",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    for to_status in [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
    ]:
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )

    async with session_maker() as session:
        await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Will be completed",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.COMPLETE,
        )

    async with session_maker() as session:
        closed = await transition_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            to_status=NcrStatus.CLOSED,
            changed_by_id=user_id,
            comments=None,
        )

    assert closed.status == NcrStatus.CLOSED
    assert closed.closed_at is not None


async def test_transition_to_closed_ignores_actions_from_other_ncrs(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """An open action on a *different* NCR must never block this one from closing --
    the guard is scoped by ncr_id, not organisation-wide."""
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import create_action, transition_ncr

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    other_ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=other_ncr_id,
            description="Open action on a different NCR",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )

    for to_status in [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
    ]:
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )

    async with session_maker() as session:
        closed = await transition_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            to_status=NcrStatus.CLOSED,
            changed_by_id=user_id,
            comments=None,
        )

    assert closed.status == NcrStatus.CLOSED


# --- Actions frozen once an NCR is closed ---------------------------------------


async def _close_ncr(
    session_maker: SessionMaker,
    *,
    organisation_id: uuid.UUID,
    ncr_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrStatus
    from app.modules.ncr.service import transition_ncr

    for to_status in [
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
        NcrStatus.CLOSED,
    ]:
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=to_status,
                changed_by_id=user_id,
                comments=None,
            )


async def test_create_action_rejects_adding_to_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A closed NCR's actions are frozen -- extending the spirit of design
    decision 4 (an independent security review found that, without this, a
    completed action could still be reopened after closure, undermining the
    close-blocked-while-actions-open guard's own guarantee)."""
    from app.modules.ncr.service import NcrActionsFrozenError, create_action

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(NcrActionsFrozenError):
            await create_action(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                description="Should not be added",
                owner_id=None,
                due_date=None,
                created_by_id=user_id,
            )


async def test_update_action_rejects_reopening_on_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrActionStatus
    from app.modules.ncr.service import (
        NcrActionsFrozenError,
        create_action,
        list_actions,
        update_action,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Will be completed then frozen",
            owner_id=None,
            due_date=None,
            created_by_id=user_id,
        )
    async with session_maker() as session:
        await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description="Will be completed then frozen",
            owner_id=None,
            due_date=None,
            status=NcrActionStatus.COMPLETE,
        )

    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(NcrActionsFrozenError):
            await update_action(
                session,
                organisation_id=organisation_id,
                action_id=action.id,
                description="Will be completed then frozen",
                owner_id=None,
                due_date=None,
                status=NcrActionStatus.OPEN,
            )

    # Confirm the reopen attempt really was rejected outright, not silently applied.
    async with session_maker() as session:
        actions, _total = await list_actions(
            session, organisation_id=organisation_id, ncr_id=ncr_id, limit=50, offset=0
        )
    assert actions[0].status == NcrActionStatus.COMPLETE


# --- Investigation tools ---------------------------------------------------------


async def test_get_investigation_tool_returns_none_when_not_started(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import get_investigation_tool

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        tool = await get_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
        )

    assert tool is None


async def test_get_investigation_tool_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import NcrNotFoundError, get_investigation_tool

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await get_investigation_tool(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                tool_type=NcrInvestigationToolType.FIVE_WHY,
            )


async def test_upsert_investigation_tool_creates_then_replaces(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import get_investigation_tool, upsert_investigation_tool

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        created = await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "The bolt sheared"},
            updated_by_id=user_id,
        )

    assert created.data == {"why_1": "The bolt sheared"}
    assert created.created_by_id == user_id
    first_id = created.id

    async with session_maker() as session:
        replaced = await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "The bolt sheared", "why_2": "Wrong torque spec"},
            updated_by_id=user_id,
        )

    # Same row, replaced -- not a second row for the same (ncr_id, tool_type).
    assert replaced.id == first_id
    assert replaced.data == {"why_1": "The bolt sheared", "why_2": "Wrong torque spec"}

    async with session_maker() as session:
        fetched = await get_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
        )
    assert fetched is not None
    assert fetched.data == {"why_1": "The bolt sheared", "why_2": "Wrong torque spec"}


async def test_upsert_investigation_tool_keeps_tool_types_independent(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import upsert_investigation_tool

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "A"},
            updated_by_id=user_id,
        )
    async with session_maker() as session:
        fishbone = await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FISHBONE,
            data={"categories": ["Machine", "Method"]},
            updated_by_id=user_id,
        )

    assert fishbone.data == {"categories": ["Machine", "Method"]}


async def test_upsert_investigation_tool_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import NcrNotFoundError, upsert_investigation_tool

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await upsert_investigation_tool(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                tool_type=NcrInvestigationToolType.FIVE_WHY,
                data={},
                updated_by_id=user_id,
            )


async def test_upsert_investigation_tool_rejects_editing_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Independent security review found this slice had no equivalent to
    create_action/update_action's frozen-once-closed rule, which would let a
    closed NCR's investigation worksheet be silently rewritten after closure."""
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import (
        NcrInvestigationToolFrozenError,
        get_investigation_tool,
        upsert_investigation_tool,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "Original"},
            updated_by_id=user_id,
        )

    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(NcrInvestigationToolFrozenError):
            await upsert_investigation_tool(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                tool_type=NcrInvestigationToolType.FIVE_WHY,
                data={"why_1": "Tampered after closure"},
                updated_by_id=user_id,
            )

    # Confirm the rewrite attempt really was rejected outright, not silently applied.
    async with session_maker() as session:
        fetched = await get_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
        )
    assert fetched is not None
    assert fetched.data == {"why_1": "Original"}


async def test_get_investigation_tool_still_readable_on_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Only writes are frozen once an NCR is closed -- reading a closed NCR's
    investigation tools (e.g. for the PDF export slice) must still work."""
    from app.modules.ncr.models import NcrInvestigationToolType
    from app.modules.ncr.service import get_investigation_tool, upsert_investigation_tool

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "Root cause"},
            updated_by_id=user_id,
        )

    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        fetched = await get_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
        )
    assert fetched is not None
    assert fetched.data == {"why_1": "Root cause"}


# --- Attachments -----------------------------------------------------------------


async def test_create_attachment_defaults(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import create_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        attachment = await create_attachment(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            document_id=document_id,
            description="Photo of the defect",
            created_by_id=user_id,
        )

    assert attachment.document_id == document_id
    assert attachment.description == "Photo of the defect"
    assert attachment.created_by_id == user_id


async def test_create_attachment_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, create_attachment

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await create_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                document_id=document_id,
                description=None,
                created_by_id=user_id,
            )


async def test_create_attachment_rejects_document_in_another_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    other_org_document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrAttachmentDocumentNotFoundError, create_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(NcrAttachmentDocumentNotFoundError):
            await create_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                document_id=other_org_document_id,
                description=None,
                created_by_id=user_id,
            )


async def test_create_attachment_rejects_duplicate_document(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrAttachmentAlreadyExistsError, create_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await create_attachment(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            document_id=document_id,
            description=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        with pytest.raises(NcrAttachmentAlreadyExistsError):
            await create_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                document_id=document_id,
                description="Duplicate",
                created_by_id=user_id,
            )


async def test_create_attachment_rejects_adding_to_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrAttachmentsFrozenError, create_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(NcrAttachmentsFrozenError):
            await create_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                document_id=document_id,
                description=None,
                created_by_id=user_id,
            )


async def test_list_attachments_raises_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import NcrNotFoundError, list_attachments

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await list_attachments(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                limit=50,
                offset=0,
            )


async def test_delete_attachment_removes_the_row(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import create_attachment, delete_attachment, list_attachments

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        attachment = await create_attachment(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            document_id=document_id,
            description=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        await delete_attachment(
            session, organisation_id=organisation_id, ncr_id=ncr_id, attachment_id=attachment.id
        )

    async with session_maker() as session:
        attachments, total = await list_attachments(
            session, organisation_id=organisation_id, ncr_id=ncr_id, limit=50, offset=0
        )
    assert total == 0
    assert attachments == []


async def test_delete_attachment_returns_ncr_not_found_for_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """`ncr_id` itself belonging to another organisation 404s via the same
    `NcrNotFoundError` every other cross-org NCR lookup raises -- checked before
    the attachment id is even looked at."""
    from app.modules.ncr.service import (
        NcrNotFoundError,
        create_attachment,
        delete_attachment,
    )

    other_raised_by_id = await _create_person(session_maker, organisation_id=other_organisation_id)
    other_document_id = await _create_document(session_maker, organisation_id=other_organisation_id)
    other_ncr_id = await _create_ncr(
        session_maker,
        organisation_id=other_organisation_id,
        raised_by_id=other_raised_by_id,
        user_id=user_id,
    )
    async with session_maker() as session:
        attachment = await create_attachment(
            session,
            organisation_id=other_organisation_id,
            ncr_id=other_ncr_id,
            document_id=other_document_id,
            description=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await delete_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=other_ncr_id,
                attachment_id=attachment.id,
            )


async def test_delete_attachment_raises_not_found_for_an_unknown_attachment_id(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A random/nonexistent attachment id for an NCR that *is* in the caller's own
    organisation 404s via NcrAttachmentNotFoundError."""
    from app.modules.ncr.service import NcrAttachmentNotFoundError, delete_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(NcrAttachmentNotFoundError):
            await delete_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                attachment_id=uuid.uuid4(),
            )


async def test_delete_attachment_rejects_editing_a_closed_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.service import (
        NcrAttachmentsFrozenError,
        create_attachment,
        delete_attachment,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        attachment = await create_attachment(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            document_id=document_id,
            description=None,
            created_by_id=user_id,
        )

    await _close_ncr(session_maker, organisation_id=organisation_id, ncr_id=ncr_id, user_id=user_id)

    async with session_maker() as session:
        with pytest.raises(NcrAttachmentsFrozenError):
            await delete_attachment(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                attachment_id=attachment.id,
            )
