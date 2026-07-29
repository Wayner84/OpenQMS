"""Unit tests for app/modules/suppliers/service.py (SQLite, ORM-level only).

Per docs/modules/Suppliers.md and the Milestone 3 plan
(.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md#1-suppliers-schema):
organisation-scoped CRUD for suppliers/certifications/performance records,
`company_id`/`certificate_document_id` validated against the People/Document
Management modules' own services (never their models directly), cross-organisation
lookups raising a not-found error, and the certification-expiry window calculation.
"""

import datetime
import decimal
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
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


async def _create_company(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company

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
        return company.id


@pytest.fixture
async def company_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_company(session_maker, organisation_id=organisation_id)


@pytest.fixture
async def other_org_company_id(
    session_maker: SessionMaker, other_organisation_id: uuid.UUID
) -> uuid.UUID:
    return await _create_company(session_maker, organisation_id=other_organisation_id)


@pytest.fixture
async def document_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="ISO 9001 Certificate",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        return document.id


# --- Suppliers -----------------------------------------------------------------


async def test_create_supplier_validates_company_and_sets_defaults(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import create_supplier

    async with session_maker() as session:
        supplier = await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=company_id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=user_id,
        )

    assert supplier.company_id == company_id
    assert supplier.approval_status == ApprovalStatus.PENDING
    assert supplier.created_by_id == user_id
    assert supplier.updated_by_id == user_id


async def test_create_supplier_rejects_company_in_another_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_org_company_id: uuid.UUID
) -> None:
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import SupplierCompanyNotFoundError, create_supplier

    async with session_maker() as session:
        with pytest.raises(SupplierCompanyNotFoundError):
            await create_supplier(
                session,
                organisation_id=organisation_id,
                company_id=other_org_company_id,
                approval_status=ApprovalStatus.PENDING,
                risk_rating=None,
                is_preferred=False,
                notes=None,
                created_by_id=None,
            )


async def test_get_supplier_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    other_org_company_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import SupplierNotFoundError, create_supplier, get_supplier

    async with session_maker() as session:
        supplier = await create_supplier(
            session,
            organisation_id=other_organisation_id,
            company_id=other_org_company_id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(SupplierNotFoundError):
            await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier.id)


async def test_list_suppliers_filters_by_status_rating_preferred_and_search(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company
    from app.modules.suppliers.models import ApprovalStatus, RiskRating
    from app.modules.suppliers.service import create_supplier, list_suppliers

    async with session_maker() as session:
        acme = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.SUPPLIER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )
        globex = await create_company(
            session,
            organisation_id=organisation_id,
            name="Globex Corp",
            type=CompanyType.SUPPLIER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )
        await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=acme.id,
            approval_status=ApprovalStatus.APPROVED,
            risk_rating=RiskRating.LOW,
            is_preferred=True,
            notes=None,
            created_by_id=None,
        )
        await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=globex.id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=RiskRating.HIGH,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        approved, approved_total = await list_suppliers(
            session,
            organisation_id=organisation_id,
            approval_status=ApprovalStatus.APPROVED,
            risk_rating=None,
            is_preferred=None,
            search=None,
            limit=50,
            offset=0,
        )
        preferred, preferred_total = await list_suppliers(
            session,
            organisation_id=organisation_id,
            approval_status=None,
            risk_rating=None,
            is_preferred=True,
            search=None,
            limit=50,
            offset=0,
        )
        searched, searched_total = await list_suppliers(
            session,
            organisation_id=organisation_id,
            approval_status=None,
            risk_rating=None,
            is_preferred=None,
            search="globex",
            limit=50,
            offset=0,
        )

    assert approved_total == 1
    assert approved[0].company_id == acme.id
    assert preferred_total == 1
    assert preferred[0].company_id == acme.id
    assert searched_total == 1
    assert searched[0].company_id == globex.id


async def test_update_supplier_changes_fields_and_updater(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.models import ApprovalStatus, RiskRating
    from app.modules.suppliers.service import create_supplier, update_supplier

    async with session_maker() as session:
        supplier = await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=company_id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        updated = await update_supplier(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier.id,
            updated_by_id=user_id,
            company_id=company_id,
            approval_status=ApprovalStatus.APPROVED,
            risk_rating=RiskRating.MEDIUM,
            is_preferred=True,
            notes="Reviewed annually",
        )

    assert updated.approval_status == ApprovalStatus.APPROVED
    assert updated.risk_rating == RiskRating.MEDIUM
    assert updated.is_preferred is True
    assert updated.updated_by_id == user_id


async def test_delete_supplier_removes_the_row(
    session_maker: SessionMaker, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import (
        SupplierNotFoundError,
        create_supplier,
        delete_supplier,
        get_supplier,
    )

    async with session_maker() as session:
        supplier = await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=company_id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        await delete_supplier(session, organisation_id=organisation_id, supplier_id=supplier.id)

    async with session_maker() as session:
        with pytest.raises(SupplierNotFoundError):
            await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier.id)


# --- Certifications --------------------------------------------------------------


async def _create_supplier(
    session_maker: SessionMaker, *, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> uuid.UUID:
    from app.modules.suppliers.models import ApprovalStatus
    from app.modules.suppliers.service import create_supplier

    async with session_maker() as session:
        supplier = await create_supplier(
            session,
            organisation_id=organisation_id,
            company_id=company_id,
            approval_status=ApprovalStatus.PENDING,
            risk_rating=None,
            is_preferred=False,
            notes=None,
            created_by_id=None,
        )
        return supplier.id


async def test_create_certification_validates_document_in_same_organisation(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
) -> None:
    from app.modules.documents.service import create_document
    from app.modules.suppliers.service import CertificateDocumentNotFoundError, create_certification

    supplier_id = await _create_supplier(
        session_maker, organisation_id=organisation_id, company_id=company_id
    )

    async with session_maker() as session:
        other_org_document = await create_document(
            session,
            organisation_id=other_organisation_id,
            title="Not in this org",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CertificateDocumentNotFoundError):
            await create_certification(
                session,
                organisation_id=organisation_id,
                supplier_id=supplier_id,
                certification_type="ISO 9001",
                certificate_document_id=other_org_document.id,
                issued_date=None,
                expiry_date=None,
            )


async def test_create_certification_raises_not_found_for_cross_organisation_supplier(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    other_org_company_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.service import SupplierNotFoundError, create_certification

    supplier_id = await _create_supplier(
        session_maker, organisation_id=other_organisation_id, company_id=other_org_company_id
    )

    async with session_maker() as session:
        with pytest.raises(SupplierNotFoundError):
            await create_certification(
                session,
                organisation_id=organisation_id,
                supplier_id=supplier_id,
                certification_type="ISO 9001",
                certificate_document_id=None,
                issued_date=None,
                expiry_date=None,
            )


async def test_update_and_delete_certification_round_trip(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.service import (
        SupplierCertificationNotFoundError,
        create_certification,
        delete_certification,
        get_certification,
        update_certification,
    )

    supplier_id = await _create_supplier(
        session_maker, organisation_id=organisation_id, company_id=company_id
    )

    async with session_maker() as session:
        certification = await create_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_type="ISO 9001",
            certificate_document_id=None,
            issued_date=datetime.date(2026, 1, 1),
            expiry_date=datetime.date(2027, 1, 1),
        )

    async with session_maker() as session:
        updated = await update_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_id=certification.id,
            certification_type="AS9100",
            certificate_document_id=document_id,
            issued_date=datetime.date(2026, 2, 1),
            expiry_date=datetime.date(2027, 2, 1),
        )

    assert updated.certification_type == "AS9100"
    assert updated.certificate_document_id == document_id

    async with session_maker() as session:
        await delete_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_id=certification.id,
        )

    async with session_maker() as session:
        with pytest.raises(SupplierCertificationNotFoundError):
            await get_certification(
                session,
                organisation_id=organisation_id,
                supplier_id=supplier_id,
                certification_id=certification.id,
            )


async def test_list_expiring_certifications_uses_configured_window_and_excludes_far_future(
    session_maker: SessionMaker, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    from app.modules.suppliers.service import create_certification, list_expiring_certifications

    supplier_id = await _create_supplier(
        session_maker, organisation_id=organisation_id, company_id=company_id
    )
    today = datetime.datetime.now(datetime.UTC).date()

    async with session_maker() as session:
        await create_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_type="Expiring soon",
            certificate_document_id=None,
            issued_date=None,
            expiry_date=today + datetime.timedelta(days=10),
        )
        await create_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_type="Far future",
            certificate_document_id=None,
            issued_date=None,
            expiry_date=today + datetime.timedelta(days=400),
        )
        await create_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_type="No expiry",
            certificate_document_id=None,
            issued_date=None,
            expiry_date=None,
        )

    async with session_maker() as session:
        # No configuration row seeded in this SQLite fixture -> falls back to the
        # built-in default (30 days), per app/modules/suppliers/reminder_config.py.
        expiring, total = await list_expiring_certifications(
            session, organisation_id=organisation_id, within_days=None, limit=50, offset=0
        )

    assert total == 1
    assert expiring[0].certification_type == "Expiring soon"


async def test_list_expiring_certifications_honours_explicit_within_days(
    session_maker: SessionMaker, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    from app.modules.suppliers.service import create_certification, list_expiring_certifications

    supplier_id = await _create_supplier(
        session_maker, organisation_id=organisation_id, company_id=company_id
    )
    today = datetime.datetime.now(datetime.UTC).date()

    async with session_maker() as session:
        await create_certification(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            certification_type="In 100 days",
            certificate_document_id=None,
            issued_date=None,
            expiry_date=today + datetime.timedelta(days=100),
        )

    async with session_maker() as session:
        excluded, excluded_total = await list_expiring_certifications(
            session, organisation_id=organisation_id, within_days=30, limit=50, offset=0
        )
        included, included_total = await list_expiring_certifications(
            session, organisation_id=organisation_id, within_days=200, limit=50, offset=0
        )

    assert excluded_total == 0
    assert included_total == 1
    assert included[0].certification_type == "In 100 days"


# --- Performance records ----------------------------------------------------------


async def test_create_and_list_performance_records_newest_first(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """SQLite's `CURRENT_TIMESTAMP` (backing `func.now()`) only has one-second
    resolution, unlike PostgreSQL's microsecond resolution -- two records created
    back-to-back in the same test can tie. Backdate the first record's `created_at`
    directly so the "newest first" ordering under test is deterministic here, while
    the real-PostgreSQL integration test proves the same ordering without needing
    to fake anything."""
    from sqlalchemy import update

    from app.modules.suppliers.models import SupplierPerformanceRecord
    from app.modules.suppliers.service import create_performance_record, list_performance_records

    supplier_id = await _create_supplier(
        session_maker, organisation_id=organisation_id, company_id=company_id
    )

    async with session_maker() as session:
        first = await create_performance_record(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            period="2026-Q1",
            score=decimal.Decimal("80.00"),
            notes=None,
            created_by_id=user_id,
        )
        await session.execute(
            update(SupplierPerformanceRecord)
            .where(SupplierPerformanceRecord.id == first.id)
            .values(created_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1))
        )
        await session.commit()
        await create_performance_record(
            session,
            organisation_id=organisation_id,
            supplier_id=supplier_id,
            period="2026-Q2",
            score=decimal.Decimal("90.00"),
            notes=None,
            created_by_id=user_id,
        )

    async with session_maker() as session:
        records, total = await list_performance_records(
            session, organisation_id=organisation_id, supplier_id=supplier_id, limit=50, offset=0
        )

    assert total == 2
    assert records[0].period == "2026-Q2"
    assert records[1].period == "2026-Q1"
    assert all(r.created_by_id == user_id for r in records)


async def test_create_performance_record_raises_not_found_for_cross_organisation_supplier(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    other_org_company_id: uuid.UUID,
) -> None:
    from app.modules.suppliers.service import SupplierNotFoundError, create_performance_record

    supplier_id = await _create_supplier(
        session_maker, organisation_id=other_organisation_id, company_id=other_org_company_id
    )

    async with session_maker() as session:
        with pytest.raises(SupplierNotFoundError):
            await create_performance_record(
                session,
                organisation_id=organisation_id,
                supplier_id=supplier_id,
                period="2026-Q1",
                score=decimal.Decimal("50.00"),
                notes=None,
                created_by_id=None,
            )
