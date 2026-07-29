"""Unit tests for app/modules/products/service.py (SQLite, ORM-level only).

Per docs/modules/Products.md and the Milestone 3 plan
(.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md#2-products-schema):
organisation-scoped CRUD for categories/products, the `part_number` uniqueness `409`,
the category "still referenced" delete guard, `document_id`/`supplier_id` validated
against the Document Management/Suppliers modules' own services (never their models
directly), and cross-organisation lookups raising a not-found error.
"""

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


async def _create_document(session_maker: SessionMaker, *, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Drawing",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        return document.id


@pytest.fixture
async def document_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    return await _create_document(session_maker, organisation_id=organisation_id)


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


async def _create_product(
    session_maker: SessionMaker,
    *,
    organisation_id: uuid.UUID,
    part_number: str = "PN-001",
    category_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from app.modules.products.models import ProductType
    from app.modules.products.service import create_product

    async with session_maker() as session:
        product = await create_product(
            session,
            organisation_id=organisation_id,
            part_number=part_number,
            description="A widget",
            revision="A",
            category_id=category_id,
            type=ProductType.INTERNAL,
            manufacturing_notes=None,
            created_by_id=None,
        )
        return product.id


# --- Categories --------------------------------------------------------------


async def test_create_and_get_category(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import create_category, get_category

    async with session_maker() as session:
        category = await create_category(session, organisation_id=organisation_id, name="Fasteners")

    async with session_maker() as session:
        fetched = await get_category(
            session, organisation_id=organisation_id, category_id=category.id
        )

    assert fetched.name == "Fasteners"


async def test_get_category_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        ProductCategoryNotFoundError,
        create_category,
        get_category,
    )

    async with session_maker() as session:
        category = await create_category(
            session, organisation_id=other_organisation_id, name="Other Org Category"
        )

    async with session_maker() as session:
        with pytest.raises(ProductCategoryNotFoundError):
            await get_category(session, organisation_id=organisation_id, category_id=category.id)


async def test_delete_category_rejects_when_referenced_by_product(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        ProductCategoryInUseError,
        create_category,
        delete_category,
    )

    async with session_maker() as session:
        category = await create_category(session, organisation_id=organisation_id, name="Fasteners")

    await _create_product(session_maker, organisation_id=organisation_id, category_id=category.id)

    async with session_maker() as session:
        with pytest.raises(ProductCategoryInUseError):
            await delete_category(session, organisation_id=organisation_id, category_id=category.id)


async def test_delete_category_succeeds_when_unused(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        ProductCategoryNotFoundError,
        create_category,
        delete_category,
        get_category,
    )

    async with session_maker() as session:
        category = await create_category(session, organisation_id=organisation_id, name="Fasteners")

    async with session_maker() as session:
        await delete_category(session, organisation_id=organisation_id, category_id=category.id)

    async with session_maker() as session:
        with pytest.raises(ProductCategoryNotFoundError):
            await get_category(session, organisation_id=organisation_id, category_id=category.id)


# --- Products ------------------------------------------------------------------


async def test_create_product_sets_default_revision_and_attribution(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import create_product

    async with session_maker() as session:
        product = await create_product(
            session,
            organisation_id=organisation_id,
            part_number="PN-100",
            description="A widget",
            revision="A",
            category_id=None,
            type=ProductType.PURCHASED,
            manufacturing_notes=None,
            created_by_id=user_id,
        )

    assert product.revision == "A"
    assert product.created_by_id == user_id
    assert product.updated_by_id == user_id


async def test_create_product_rejects_duplicate_part_number_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import ProductPartNumberConflictError, create_product

    await _create_product(session_maker, organisation_id=organisation_id, part_number="PN-DUP")

    async with session_maker() as session:
        with pytest.raises(ProductPartNumberConflictError):
            await create_product(
                session,
                organisation_id=organisation_id,
                part_number="PN-DUP",
                description="Another widget",
                revision="A",
                category_id=None,
                type=ProductType.PURCHASED,
                manufacturing_notes=None,
                created_by_id=None,
            )


async def test_create_product_allows_same_part_number_in_different_organisations(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import create_product

    await _create_product(session_maker, organisation_id=organisation_id, part_number="PN-SHARED")

    async with session_maker() as session:
        product = await create_product(
            session,
            organisation_id=other_organisation_id,
            part_number="PN-SHARED",
            description="Also a widget",
            revision="A",
            category_id=None,
            type=ProductType.PURCHASED,
            manufacturing_notes=None,
            created_by_id=None,
        )

    assert product.part_number == "PN-SHARED"


async def test_create_product_rejects_category_in_another_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import (
        ProductCategoryNotFoundError,
        create_category,
        create_product,
    )

    async with session_maker() as session:
        other_org_category = await create_category(
            session, organisation_id=other_organisation_id, name="Other Org Category"
        )

    async with session_maker() as session:
        with pytest.raises(ProductCategoryNotFoundError):
            await create_product(
                session,
                organisation_id=organisation_id,
                part_number="PN-200",
                description="A widget",
                revision="A",
                category_id=other_org_category.id,
                type=ProductType.PURCHASED,
                manufacturing_notes=None,
                created_by_id=None,
            )


async def test_get_product_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import ProductNotFoundError, get_product

    product_id = await _create_product(session_maker, organisation_id=other_organisation_id)

    async with session_maker() as session:
        with pytest.raises(ProductNotFoundError):
            await get_product(session, organisation_id=organisation_id, product_id=product_id)


async def test_list_products_filters_by_category_type_and_search(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import create_category, create_product, list_products

    async with session_maker() as session:
        category = await create_category(session, organisation_id=organisation_id, name="Fasteners")
        await create_product(
            session,
            organisation_id=organisation_id,
            part_number="BOLT-001",
            description="M6 bolt",
            revision="A",
            category_id=category.id,
            type=ProductType.PURCHASED,
            manufacturing_notes=None,
            created_by_id=None,
        )
        await create_product(
            session,
            organisation_id=organisation_id,
            part_number="BRACKET-001",
            description="Steel bracket",
            revision="A",
            category_id=None,
            type=ProductType.INTERNAL,
            manufacturing_notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        by_category, by_category_total = await list_products(
            session,
            organisation_id=organisation_id,
            category_id=category.id,
            type=None,
            search=None,
            limit=50,
            offset=0,
        )
        by_type, by_type_total = await list_products(
            session,
            organisation_id=organisation_id,
            category_id=None,
            type=ProductType.INTERNAL,
            search=None,
            limit=50,
            offset=0,
        )
        by_search, by_search_total = await list_products(
            session,
            organisation_id=organisation_id,
            category_id=None,
            type=None,
            search="bracket",
            limit=50,
            offset=0,
        )

    assert by_category_total == 1
    assert by_category[0].part_number == "BOLT-001"
    assert by_type_total == 1
    assert by_type[0].part_number == "BRACKET-001"
    assert by_search_total == 1
    assert by_search[0].part_number == "BRACKET-001"


async def test_update_product_rejects_conflicting_part_number(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import ProductPartNumberConflictError, update_product

    await _create_product(session_maker, organisation_id=organisation_id, part_number="PN-A")
    product_b_id = await _create_product(
        session_maker, organisation_id=organisation_id, part_number="PN-B"
    )

    async with session_maker() as session:
        with pytest.raises(ProductPartNumberConflictError):
            await update_product(
                session,
                organisation_id=organisation_id,
                product_id=product_b_id,
                updated_by_id=None,
                part_number="PN-A",
                description="A widget",
                revision="A",
                category_id=None,
                type=ProductType.INTERNAL,
                manufacturing_notes=None,
            )


async def test_update_product_allows_keeping_its_own_part_number(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductType
    from app.modules.products.service import update_product

    product_id = await _create_product(
        session_maker, organisation_id=organisation_id, part_number="PN-SELF"
    )

    async with session_maker() as session:
        updated = await update_product(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            updated_by_id=user_id,
            part_number="PN-SELF",
            description="Updated description",
            revision="B",
            category_id=None,
            type=ProductType.ASSEMBLY,
            manufacturing_notes="Handle with care",
        )

    assert updated.description == "Updated description"
    assert updated.revision == "B"
    assert updated.type == ProductType.ASSEMBLY
    assert updated.updated_by_id == user_id


async def test_delete_product_removes_the_row(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import ProductNotFoundError, delete_product, get_product

    product_id = await _create_product(session_maker, organisation_id=organisation_id)

    async with session_maker() as session:
        await delete_product(session, organisation_id=organisation_id, product_id=product_id)

    async with session_maker() as session:
        with pytest.raises(ProductNotFoundError):
            await get_product(session, organisation_id=organisation_id, product_id=product_id)


# --- Product-document links --------------------------------------------------------


async def test_create_product_document_link_validates_document_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductDocumentRelationshipType
    from app.modules.products.service import (
        ProductDocumentNotFoundError,
        create_product_document_link,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)
    other_org_document_id = await _create_document(
        session_maker, organisation_id=other_organisation_id
    )

    async with session_maker() as session:
        with pytest.raises(ProductDocumentNotFoundError):
            await create_product_document_link(
                session,
                organisation_id=organisation_id,
                product_id=product_id,
                document_id=other_org_document_id,
                relationship_type=ProductDocumentRelationshipType.DRAWING,
            )


async def test_create_product_document_link_rejects_duplicate_relationship_type(
    session_maker: SessionMaker, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductDocumentRelationshipType
    from app.modules.products.service import (
        ProductDocumentLinkAlreadyExistsError,
        create_product_document_link,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)

    async with session_maker() as session:
        await create_product_document_link(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            document_id=document_id,
            relationship_type=ProductDocumentRelationshipType.DRAWING,
        )

    async with session_maker() as session:
        with pytest.raises(ProductDocumentLinkAlreadyExistsError):
            await create_product_document_link(
                session,
                organisation_id=organisation_id,
                product_id=product_id,
                document_id=document_id,
                relationship_type=ProductDocumentRelationshipType.DRAWING,
            )


async def test_same_document_can_be_linked_under_two_relationship_types(
    session_maker: SessionMaker, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    from app.modules.products.models import ProductDocumentRelationshipType
    from app.modules.products.service import (
        create_product_document_link,
        list_product_document_links,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)

    async with session_maker() as session:
        await create_product_document_link(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            document_id=document_id,
            relationship_type=ProductDocumentRelationshipType.DRAWING,
        )
        await create_product_document_link(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            document_id=document_id,
            relationship_type=ProductDocumentRelationshipType.SPECIFICATION,
        )

    async with session_maker() as session:
        links, total = await list_product_document_links(
            session, organisation_id=organisation_id, product_id=product_id, limit=50, offset=0
        )

    assert total == 2


async def test_delete_product_document_link_raises_not_found_for_cross_organisation_product(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import ProductNotFoundError, delete_product_document_link

    other_org_product_id = await _create_product(
        session_maker, organisation_id=other_organisation_id
    )

    async with session_maker() as session:
        with pytest.raises(ProductNotFoundError):
            await delete_product_document_link(
                session,
                organisation_id=organisation_id,
                product_id=other_org_product_id,
                link_id=uuid.uuid4(),
            )


# --- Product-supplier links ---------------------------------------------------------


async def test_create_product_supplier_link_validates_supplier_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        ProductSupplierNotFoundError,
        create_product_supplier_link,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)
    other_org_supplier_id = await _create_supplier(
        session_maker, organisation_id=other_organisation_id
    )

    async with session_maker() as session:
        with pytest.raises(ProductSupplierNotFoundError):
            await create_product_supplier_link(
                session,
                organisation_id=organisation_id,
                product_id=product_id,
                supplier_id=other_org_supplier_id,
                is_preferred=False,
            )


async def test_create_product_supplier_link_rejects_duplicate(
    session_maker: SessionMaker, organisation_id: uuid.UUID, supplier_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        ProductSupplierLinkAlreadyExistsError,
        create_product_supplier_link,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)

    async with session_maker() as session:
        await create_product_supplier_link(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            supplier_id=supplier_id,
            is_preferred=False,
        )

    async with session_maker() as session:
        with pytest.raises(ProductSupplierLinkAlreadyExistsError):
            await create_product_supplier_link(
                session,
                organisation_id=organisation_id,
                product_id=product_id,
                supplier_id=supplier_id,
                is_preferred=True,
            )


async def test_create_and_list_and_delete_product_supplier_link(
    session_maker: SessionMaker, organisation_id: uuid.UUID, supplier_id: uuid.UUID
) -> None:
    from app.modules.products.service import (
        create_product_supplier_link,
        delete_product_supplier_link,
        list_product_supplier_links,
    )

    product_id = await _create_product(session_maker, organisation_id=organisation_id)

    async with session_maker() as session:
        link = await create_product_supplier_link(
            session,
            organisation_id=organisation_id,
            product_id=product_id,
            supplier_id=supplier_id,
            is_preferred=True,
        )

    async with session_maker() as session:
        links, total = await list_product_supplier_links(
            session, organisation_id=organisation_id, product_id=product_id, limit=50, offset=0
        )
    assert total == 1
    assert links[0].is_preferred is True

    async with session_maker() as session:
        await delete_product_supplier_link(
            session, organisation_id=organisation_id, product_id=product_id, link_id=link.id
        )

    async with session_maker() as session:
        links_after, total_after = await list_product_supplier_links(
            session, organisation_id=organisation_id, product_id=product_id, limit=50, offset=0
        )
    assert total_after == 0
    assert links_after == []
