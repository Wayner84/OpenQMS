"""Business logic for the Products module: categories, product records, and their
links to Document Management drawings/specs and Suppliers. Per
docs/modules/Products.md and the Milestone 3 plan
(.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md): every operation is
scoped to the caller's organisation; `document_id` and `supplier_id` are validated
against the Document Management and Suppliers modules' own service layers (module
boundary rule -- see docs/CodingStandards.md#backend-python), never queried
directly.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.service import DocumentNotFoundError, get_document
from app.modules.products.models import (
    Product,
    ProductCategory,
    ProductDocument,
    ProductDocumentRelationshipType,
    ProductSupplierLink,
    ProductType,
)
from app.modules.suppliers.service import SupplierNotFoundError, get_supplier


class ProductCategoryNotFoundError(Exception):
    """Raised when a product category id doesn't exist in the caller's organisation."""


class ProductCategoryInUseError(Exception):
    """Raised when deleting a category that is still referenced by a product."""


class ProductNotFoundError(Exception):
    """Raised when a product id doesn't exist in the caller's organisation."""


class ProductPartNumberConflictError(Exception):
    """Raised when creating/updating a product with a `part_number` already used by
    another product in the same organisation."""


class ProductDocumentNotFoundError(Exception):
    """Raised when a product-document link's `document_id` doesn't exist in the
    caller's organisation."""


class ProductDocumentLinkNotFoundError(Exception):
    """Raised when a product-document link id doesn't exist for the given product."""


class ProductDocumentLinkAlreadyExistsError(Exception):
    """Raised when linking a document to a product under a relationship type that's
    already linked."""


class ProductSupplierNotFoundError(Exception):
    """Raised when a product-supplier link's `supplier_id` doesn't exist in the
    caller's organisation."""


class ProductSupplierLinkNotFoundError(Exception):
    """Raised when a product-supplier link id doesn't exist for the given product."""


class ProductSupplierLinkAlreadyExistsError(Exception):
    """Raised when linking a supplier to a product that's already linked."""


# --- Categories ------------------------------------------------------------------


async def create_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, name: str
) -> ProductCategory:
    category = ProductCategory(organisation_id=organisation_id, name=name)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def get_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, category_id: uuid.UUID
) -> ProductCategory:
    category = (
        await session.execute(
            select(ProductCategory).where(
                ProductCategory.id == category_id,
                ProductCategory.organisation_id == organisation_id,
            )
        )
    ).scalar_one_or_none()
    if category is None:
        raise ProductCategoryNotFoundError(
            f"No product category {category_id} in this organisation"
        )
    return category


async def list_categories(
    session: AsyncSession, *, organisation_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[ProductCategory], int]:
    total = (
        await session.execute(
            select(func.count())
            .select_from(ProductCategory)
            .where(ProductCategory.organisation_id == organisation_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(ProductCategory)
        .where(ProductCategory.organisation_id == organisation_id)
        .order_by(ProductCategory.name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, category_id: uuid.UUID, name: str
) -> ProductCategory:
    category = await get_category(session, organisation_id=organisation_id, category_id=category_id)
    category.name = name
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(
    session: AsyncSession, *, organisation_id: uuid.UUID, category_id: uuid.UUID
) -> None:
    category = await get_category(session, organisation_id=organisation_id, category_id=category_id)

    products_count = (
        await session.execute(
            select(func.count()).select_from(Product).where(Product.category_id == category_id)
        )
    ).scalar_one()
    if products_count > 0:
        raise ProductCategoryInUseError("Cannot delete a category that is still used by a product")

    await session.delete(category)
    await session.commit()


# --- Products --------------------------------------------------------------------


async def _assert_part_number_available(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    part_number: str,
    exclude_product_id: uuid.UUID | None,
) -> None:
    filters = [Product.organisation_id == organisation_id, Product.part_number == part_number]
    if exclude_product_id is not None:
        filters.append(Product.id != exclude_product_id)
    existing = (await session.execute(select(Product).where(*filters))).scalar_one_or_none()
    if existing is not None:
        raise ProductPartNumberConflictError(
            f"A product with part number {part_number!r} already exists in this organisation"
        )


async def create_product(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    part_number: str,
    description: str,
    revision: str,
    category_id: uuid.UUID | None,
    type: ProductType,
    manufacturing_notes: str | None,
    created_by_id: uuid.UUID | None,
) -> Product:
    if category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=category_id)
    await _assert_part_number_available(
        session, organisation_id=organisation_id, part_number=part_number, exclude_product_id=None
    )

    product = Product(
        organisation_id=organisation_id,
        part_number=part_number,
        description=description,
        revision=revision,
        category_id=category_id,
        type=type,
        manufacturing_notes=manufacturing_notes,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def get_product(
    session: AsyncSession, *, organisation_id: uuid.UUID, product_id: uuid.UUID
) -> Product:
    product = (
        await session.execute(
            select(Product).where(
                Product.id == product_id, Product.organisation_id == organisation_id
            )
        )
    ).scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(f"No product {product_id} in this organisation")
    return product


async def list_products(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    category_id: uuid.UUID | None,
    type: ProductType | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    """List products, optionally filtered by exact `category_id`/`type`, and a
    case-insensitive substring `search` across `part_number`/`description`."""
    filters = [Product.organisation_id == organisation_id]
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if type is not None:
        filters.append(Product.type == type)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(Product.part_number.ilike(pattern), Product.description.ilike(pattern)))

    total = (
        await session.execute(select(func.count()).select_from(Product).where(*filters))
    ).scalar_one()
    result = await session.execute(
        select(Product).where(*filters).order_by(Product.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_product(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID,
    updated_by_id: uuid.UUID | None,
    part_number: str,
    description: str,
    revision: str,
    category_id: uuid.UUID | None,
    type: ProductType,
    manufacturing_notes: str | None,
) -> Product:
    product = await get_product(session, organisation_id=organisation_id, product_id=product_id)
    if category_id is not None:
        await get_category(session, organisation_id=organisation_id, category_id=category_id)
    await _assert_part_number_available(
        session,
        organisation_id=organisation_id,
        part_number=part_number,
        exclude_product_id=product_id,
    )

    product.part_number = part_number
    product.description = description
    product.revision = revision
    product.category_id = category_id
    product.type = type
    product.manufacturing_notes = manufacturing_notes
    product.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(
    session: AsyncSession, *, organisation_id: uuid.UUID, product_id: uuid.UUID
) -> None:
    """Hard delete: linked document/supplier link rows cascade at the DB level (`ON
    DELETE CASCADE`), since they are wholly owned by the product."""
    product = await get_product(session, organisation_id=organisation_id, product_id=product_id)
    await session.delete(product)
    await session.commit()


# --- Product-document links --------------------------------------------------------


async def create_product_document_link(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID,
    document_id: uuid.UUID,
    relationship_type: ProductDocumentRelationshipType,
) -> ProductDocument:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)
    try:
        await get_document(session, organisation_id=organisation_id, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise ProductDocumentNotFoundError(str(exc)) from exc

    existing = (
        await session.execute(
            select(ProductDocument).where(
                ProductDocument.product_id == product_id,
                ProductDocument.document_id == document_id,
                ProductDocument.relationship_type == relationship_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ProductDocumentLinkAlreadyExistsError(
            "This document is already linked to the product under this relationship type"
        )

    link = ProductDocument(
        product_id=product_id, document_id=document_id, relationship_type=relationship_type
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


async def list_product_document_links(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ProductDocument], int]:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(ProductDocument)
            .where(ProductDocument.product_id == product_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(ProductDocument)
        .where(ProductDocument.product_id == product_id)
        .order_by(ProductDocument.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def delete_product_document_link(
    session: AsyncSession, *, organisation_id: uuid.UUID, product_id: uuid.UUID, link_id: uuid.UUID
) -> None:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)
    link = (
        await session.execute(
            select(ProductDocument).where(
                ProductDocument.id == link_id, ProductDocument.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise ProductDocumentLinkNotFoundError(
            f"No document link {link_id} for product {product_id}"
        )
    await session.delete(link)
    await session.commit()


# --- Product-supplier links ---------------------------------------------------------


async def create_product_supplier_link(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
    is_preferred: bool,
) -> ProductSupplierLink:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)
    try:
        await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
    except SupplierNotFoundError as exc:
        raise ProductSupplierNotFoundError(str(exc)) from exc

    existing = (
        await session.execute(
            select(ProductSupplierLink).where(
                ProductSupplierLink.product_id == product_id,
                ProductSupplierLink.supplier_id == supplier_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ProductSupplierLinkAlreadyExistsError(
            "This supplier is already linked to the product"
        )

    link = ProductSupplierLink(
        product_id=product_id, supplier_id=supplier_id, is_preferred=is_preferred
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


async def list_product_supplier_links(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    product_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[ProductSupplierLink], int]:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(ProductSupplierLink)
            .where(ProductSupplierLink.product_id == product_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(ProductSupplierLink)
        .where(ProductSupplierLink.product_id == product_id)
        .order_by(ProductSupplierLink.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def delete_product_supplier_link(
    session: AsyncSession, *, organisation_id: uuid.UUID, product_id: uuid.UUID, link_id: uuid.UUID
) -> None:
    await get_product(session, organisation_id=organisation_id, product_id=product_id)
    link = (
        await session.execute(
            select(ProductSupplierLink).where(
                ProductSupplierLink.id == link_id, ProductSupplierLink.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise ProductSupplierLinkNotFoundError(
            f"No supplier link {link_id} for product {product_id}"
        )
    await session.delete(link)
    await session.commit()
