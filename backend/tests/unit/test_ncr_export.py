"""Unit tests for app/modules/ncr/export.py (SQLite, ORM-level for
`gather_ncr_export_data`; pure-function for `render_ncr_pdf`).

Per docs/modules/NCR.md and the Milestone 4 plan's design decision 8: an
incomplete NCR (`status != closed`) still renders every section, with a
placeholder for the parts that aren't finished yet; a closed NCR renders as a
fully-populated report. `render_ncr_pdf` is built with `pageCompression=0` so
its output's text is byte-searchable, letting these tests assert on rendered
content without a PDF parser.
"""

import datetime
import uuid
from collections.abc import AsyncIterator

import pytest
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


async def _create_person(
    session_maker: SessionMaker, *, organisation_id: uuid.UUID, first_name: str, last_name: str
) -> uuid.UUID:
    from app.modules.people.service import create_person

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name=first_name,
            last_name=last_name,
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
    return await _create_person(
        session_maker, organisation_id=organisation_id, first_name="Quinn", last_name="Reporter"
    )


@pytest.fixture
async def owner_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_person(
        session_maker, organisation_id=organisation_id, first_name="Owen", last_name="Actioner"
    )


@pytest.fixture
async def product_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
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
async def supplier_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
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


async def _create_document(
    session_maker: SessionMaker, *, organisation_id: uuid.UUID, title: str = "Inspection photo"
) -> uuid.UUID:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title=title,
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        return document.id


@pytest.fixture
async def document_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_document(session_maker, organisation_id=organisation_id)


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


# --- gather_ncr_export_data ---------------------------------------------------


async def test_gather_export_data_resolves_raised_by_product_and_supplier_labels(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    product_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import gather_ncr_export_data

    ncr_id = await _create_ncr(
        session_maker,
        organisation_id=organisation_id,
        raised_by_id=raised_by_id,
        user_id=user_id,
        product_id=product_id,
    )

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    assert data.raised_by_name == "Quinn Reporter"
    assert data.product_label is not None
    assert "PN-001" in data.product_label
    assert data.supplier_label is None


async def test_gather_export_data_resolves_supplier_company_name(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    supplier_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import gather_ncr_export_data
    from app.modules.ncr.models import NcrType

    ncr_id = await _create_ncr(
        session_maker,
        organisation_id=organisation_id,
        raised_by_id=raised_by_id,
        user_id=user_id,
        type=NcrType.SUPPLIER,
        supplier_id=supplier_id,
    )

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    assert data.supplier_label == "Acme Supplies Ltd"


async def test_gather_export_data_raises_not_found_for_a_cross_organisation_ncr(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    other_organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import gather_ncr_export_data
    from app.modules.ncr.service import NcrNotFoundError

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )

    async with session_maker() as session:
        with pytest.raises(NcrNotFoundError):
            await gather_ncr_export_data(
                session, organisation_id=other_organisation_id, ncr_id=ncr_id
            )


async def test_gather_export_data_resolves_attachment_document_titles(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import gather_ncr_export_data
    from app.modules.ncr.service import create_attachment

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        await create_attachment(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            document_id=document_id,
            description="Photo of the defect",
            created_by_id=user_id,
        )

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    assert len(data.attachments) == 1
    attachment, title = data.attachments[0]
    assert title == "Inspection photo"
    assert attachment.description == "Photo of the defect"


async def test_gather_export_data_falls_back_when_an_attached_document_is_later_deleted(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """A document attached to an NCR can later be independently soft-deleted (the
    Document Management module has no awareness of NCR attachments, per the
    module-isolation rule) -- export must not 500 in that case."""
    from app.modules.documents.service import delete_document
    from app.modules.ncr.export import DOCUMENT_UNAVAILABLE, gather_ncr_export_data
    from app.modules.ncr.service import create_attachment

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
        await delete_document(session, organisation_id=organisation_id, document_id=document_id)

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    assert data.attachments[0][1] == DOCUMENT_UNAVAILABLE


# --- render_ncr_pdf ------------------------------------------------------------


async def test_render_pdf_for_an_open_ncr_shows_placeholders_for_unfinished_sections(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import (
        NOT_STARTED,
        NOT_YET_COMPLETED,
        gather_ncr_export_data,
        render_ncr_pdf,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    pdf_bytes = render_ncr_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")
    assert data.ncr.number.encode() in pdf_bytes
    assert NOT_YET_COMPLETED.encode() in pdf_bytes
    assert NOT_STARTED.encode() in pdf_bytes


async def test_render_pdf_for_a_closed_ncr_shows_populated_content(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    owner_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    from app.modules.ncr.export import NOT_STARTED, gather_ncr_export_data, render_ncr_pdf
    from app.modules.ncr.models import (
        NcrActionStatus,
        NcrInvestigationToolType,
        NcrStatus,
        NcrType,
    )
    from app.modules.ncr.service import (
        create_action,
        transition_ncr,
        update_action,
        update_ncr,
        upsert_investigation_tool,
    )

    ncr_id = await _create_ncr(
        session_maker, organisation_id=organisation_id, raised_by_id=raised_by_id, user_id=user_id
    )
    async with session_maker() as session:
        action = await create_action(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            description="Quarantine the affected batch",
            owner_id=owner_id,
            due_date=datetime.date(2026, 8, 1),
            created_by_id=user_id,
        )
    async with session_maker() as session:
        await update_action(
            session,
            organisation_id=organisation_id,
            action_id=action.id,
            description=action.description,
            owner_id=owner_id,
            due_date=action.due_date,
            status=NcrActionStatus.COMPLETE,
        )
    async with session_maker() as session:
        await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"why_1": "The seal failed"},
            updated_by_id=user_id,
        )
    async with session_maker() as session:
        await update_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            updated_by_id=user_id,
            type=NcrType.INTERNAL,
            product_id=None,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="A widget was out of spec",
            root_cause_summary="A worn seal caused the leak",
        )
    for target_status in (
        NcrStatus.INVESTIGATE,
        NcrStatus.CONTAINMENT,
        NcrStatus.CORRECTIVE_ACTION,
        NcrStatus.VERIFICATION,
        NcrStatus.CLOSED,
    ):
        async with session_maker() as session:
            await transition_ncr(
                session,
                organisation_id=organisation_id,
                ncr_id=ncr_id,
                to_status=target_status,
                changed_by_id=user_id,
                comments=None,
            )

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    pdf_bytes = render_ncr_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"A worn seal caused the leak" in pdf_bytes
    assert b"Quarantine the affected batch" in pdf_bytes
    assert b"Owen Actioner" in pdf_bytes
    assert b"The seal failed" in pdf_bytes
    # Fishbone/8D/10D were never started, even though 5 Why was.
    assert NOT_STARTED.encode() in pdf_bytes


async def test_render_pdf_escapes_user_text_that_looks_like_markup(
    session_maker: SessionMaker,
    organisation_id: uuid.UUID,
    raised_by_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """`reportlab`'s `Paragraph` interprets a constrained HTML-like markup in its
    input string -- an NCR description or investigation-tool value containing
    something it parses as an unterminated tag (e.g. a literal "<b>" typed as
    plain text) would otherwise raise `ValueError` and 500 the whole export.
    User-controlled text must be escaped before being interpolated into a
    `Paragraph`."""
    from app.modules.ncr.export import gather_ncr_export_data, render_ncr_pdf
    from app.modules.ncr.models import NcrInvestigationToolType, NcrType
    from app.modules.ncr.service import update_ncr, upsert_investigation_tool

    ncr_id = await _create_ncr(
        session_maker,
        organisation_id=organisation_id,
        raised_by_id=raised_by_id,
        user_id=user_id,
        description="Gap measured <b>0.5mm out of tolerance",
    )
    async with session_maker() as session:
        await update_ncr(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            updated_by_id=user_id,
            type=NcrType.INTERNAL,
            product_id=None,
            supplier_id=None,
            raised_by_id=raised_by_id,
            description="Gap measured <b>0.5mm out of tolerance",
            root_cause_summary="Tolerance was <i>tighter than the process allows",
        )
    async with session_maker() as session:
        await upsert_investigation_tool(
            session,
            organisation_id=organisation_id,
            ncr_id=ncr_id,
            tool_type=NcrInvestigationToolType.FIVE_WHY,
            data={"<why_1>": "Because <b>it failed"},
            updated_by_id=user_id,
        )

    async with session_maker() as session:
        data = await gather_ncr_export_data(session, organisation_id=organisation_id, ncr_id=ncr_id)

    # Must not raise -- this is the regression this test protects against.
    pdf_bytes = render_ncr_pdf(data)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"Gap measured" in pdf_bytes
