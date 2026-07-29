"""Products endpoints: categories, product records, and their links to Document
Management drawings/specs and Suppliers.

Per docs/API.md and the Milestone 3 plan's design decision 2: every operation here
requires only authentication (any active user), not admin privilege -- matching
Suppliers/People's precedent, not Document Management's admin-gated categories/tags.
Every guard is still fully re-enforced server-side and scoped to
`current_user.organisation_id`, never a client-supplied value.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser
from app.modules.products.models import ProductType
from app.modules.products.schemas import (
    ProductCategoryListResponse,
    ProductCategoryRead,
    ProductCategoryWriteRequest,
    ProductDocumentLinkCreateRequest,
    ProductDocumentLinkListResponse,
    ProductDocumentLinkRead,
    ProductListResponse,
    ProductRead,
    ProductSupplierLinkCreateRequest,
    ProductSupplierLinkListResponse,
    ProductSupplierLinkRead,
    ProductWriteRequest,
)
from app.modules.products.service import (
    ProductCategoryInUseError,
    ProductCategoryNotFoundError,
    ProductDocumentLinkAlreadyExistsError,
    ProductDocumentLinkNotFoundError,
    ProductDocumentNotFoundError,
    ProductNotFoundError,
    ProductPartNumberConflictError,
    ProductSupplierLinkAlreadyExistsError,
    ProductSupplierLinkNotFoundError,
    ProductSupplierNotFoundError,
    create_category,
    create_product,
    create_product_document_link,
    create_product_supplier_link,
    delete_category,
    delete_product,
    delete_product_document_link,
    delete_product_supplier_link,
    get_category,
    get_product,
    list_categories,
    list_product_document_links,
    list_product_supplier_links,
    list_products,
    update_category,
    update_product,
)

categories_router = APIRouter(prefix="/product-categories", tags=["products"])
products_router = APIRouter(prefix="/products", tags=["products"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


# --- Categories --------------------------------------------------------------


@categories_router.post("", status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(
    payload: ProductCategoryWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> ProductCategoryRead:
    category = await create_category(
        session, organisation_id=current_user.organisation_id, name=payload.name
    )
    return ProductCategoryRead.model_validate(category)


@categories_router.get("")
async def list_categories_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductCategoryListResponse:
    categories, total = await list_categories(
        session, organisation_id=current_user.organisation_id, limit=limit, offset=offset
    )
    return ProductCategoryListResponse(
        items=[ProductCategoryRead.model_validate(c) for c in categories],
        total=total,
        limit=limit,
        offset=offset,
    )


@categories_router.get("/{category_id}")
async def get_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> ProductCategoryRead:
    try:
        category = await get_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except ProductCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product category not found"
        ) from exc
    return ProductCategoryRead.model_validate(category)


@categories_router.patch("/{category_id}")
async def update_category_endpoint(
    category_id: uuid.UUID,
    payload: ProductCategoryWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> ProductCategoryRead:
    try:
        category = await update_category(
            session,
            organisation_id=current_user.organisation_id,
            category_id=category_id,
            name=payload.name,
        )
    except ProductCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product category not found"
        ) from exc
    return ProductCategoryRead.model_validate(category)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await delete_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except ProductCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product category not found"
        ) from exc
    except ProductCategoryInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# --- Products ------------------------------------------------------------------


@products_router.post("", status_code=status.HTTP_201_CREATED)
async def create_product_endpoint(
    payload: ProductWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> ProductRead:
    try:
        product = await create_product(
            session,
            organisation_id=current_user.organisation_id,
            part_number=payload.part_number,
            description=payload.description,
            revision=payload.revision,
            category_id=payload.category_id,
            type=payload.type,
            manufacturing_notes=payload.manufacturing_notes,
            created_by_id=current_user.id,
        )
    except ProductCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product category not found"
        ) from exc
    except ProductPartNumberConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProductRead.model_validate(product)


@products_router.get("")
async def list_products_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    category_id: uuid.UUID | None = None,
    type: ProductType | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductListResponse:
    products, total = await list_products(
        session,
        organisation_id=current_user.organisation_id,
        category_id=category_id,
        type=type,
        search=search,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(
        items=[ProductRead.model_validate(p) for p in products],
        total=total,
        limit=limit,
        offset=offset,
    )


@products_router.get("/{product_id}")
async def get_product_endpoint(
    product_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> ProductRead:
    try:
        product = await get_product(
            session, organisation_id=current_user.organisation_id, product_id=product_id
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    return ProductRead.model_validate(product)


@products_router.patch("/{product_id}")
async def update_product_endpoint(
    product_id: uuid.UUID,
    payload: ProductWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> ProductRead:
    try:
        product = await update_product(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            updated_by_id=current_user.id,
            part_number=payload.part_number,
            description=payload.description,
            revision=payload.revision,
            category_id=payload.category_id,
            type=payload.type,
            manufacturing_notes=payload.manufacturing_notes,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    except ProductCategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product category not found"
        ) from exc
    except ProductPartNumberConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProductRead.model_validate(product)


@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_endpoint(
    product_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await delete_product(
            session, organisation_id=current_user.organisation_id, product_id=product_id
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc


# --- Product-document links --------------------------------------------------------


@products_router.post("/{product_id}/documents", status_code=status.HTTP_201_CREATED)
async def create_product_document_link_endpoint(
    product_id: uuid.UUID,
    payload: ProductDocumentLinkCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> ProductDocumentLinkRead:
    try:
        link = await create_product_document_link(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            document_id=payload.document_id,
            relationship_type=payload.relationship_type,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    except ProductDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except ProductDocumentLinkAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProductDocumentLinkRead.model_validate(link)


@products_router.get("/{product_id}/documents")
async def list_product_document_links_endpoint(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductDocumentLinkListResponse:
    try:
        links, total = await list_product_document_links(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            limit=limit,
            offset=offset,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    return ProductDocumentLinkListResponse(
        items=[ProductDocumentLinkRead.model_validate(link) for link in links],
        total=total,
        limit=limit,
        offset=offset,
    )


@products_router.delete("/{product_id}/documents/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_document_link_endpoint(
    product_id: uuid.UUID,
    link_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> None:
    try:
        await delete_product_document_link(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            link_id=link_id,
        )
    except (ProductNotFoundError, ProductDocumentLinkNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document link not found"
        ) from exc


# --- Product-supplier links ---------------------------------------------------------


@products_router.post("/{product_id}/suppliers", status_code=status.HTTP_201_CREATED)
async def create_product_supplier_link_endpoint(
    product_id: uuid.UUID,
    payload: ProductSupplierLinkCreateRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> ProductSupplierLinkRead:
    try:
        link = await create_product_supplier_link(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            supplier_id=payload.supplier_id,
            is_preferred=payload.is_preferred,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    except ProductSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except ProductSupplierLinkAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProductSupplierLinkRead.model_validate(link)


@products_router.get("/{product_id}/suppliers")
async def list_product_supplier_links_endpoint(
    product_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductSupplierLinkListResponse:
    try:
        links, total = await list_product_supplier_links(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            limit=limit,
            offset=offset,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from exc
    return ProductSupplierLinkListResponse(
        items=[ProductSupplierLinkRead.model_validate(link) for link in links],
        total=total,
        limit=limit,
        offset=offset,
    )


@products_router.delete("/{product_id}/suppliers/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_supplier_link_endpoint(
    product_id: uuid.UUID,
    link_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> None:
    try:
        await delete_product_supplier_link(
            session,
            organisation_id=current_user.organisation_id,
            product_id=product_id,
            link_id=link_id,
        )
    except (ProductNotFoundError, ProductSupplierLinkNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier link not found"
        ) from exc
