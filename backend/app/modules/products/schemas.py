"""Pydantic schemas for the Products module, per docs/modules/Products.md and
docs/API.md."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.modules.products.models import ProductDocumentRelationshipType, ProductType


class ProductCategoryWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/product-categories."""

    name: str


class ProductCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    name: str


class ProductCategoryListResponse(BaseModel):
    items: list[ProductCategoryRead]
    total: int
    limit: int
    offset: int


class ProductWriteRequest(BaseModel):
    """Shared shape for POST and PATCH /api/v1/products (create and full update)."""

    part_number: str
    description: str
    revision: str = "A"
    category_id: uuid.UUID | None = None
    type: ProductType
    manufacturing_notes: str | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    part_number: str
    description: str
    revision: str
    category_id: uuid.UUID | None
    type: ProductType
    manufacturing_notes: str | None
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


class ProductDocumentLinkCreateRequest(BaseModel):
    document_id: uuid.UUID
    relationship_type: ProductDocumentRelationshipType


class ProductDocumentLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    document_id: uuid.UUID
    relationship_type: ProductDocumentRelationshipType


class ProductDocumentLinkListResponse(BaseModel):
    items: list[ProductDocumentLinkRead]
    total: int
    limit: int
    offset: int


class ProductSupplierLinkCreateRequest(BaseModel):
    supplier_id: uuid.UUID
    is_preferred: bool = False


class ProductSupplierLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID
    is_preferred: bool


class ProductSupplierLinkListResponse(BaseModel):
    items: list[ProductSupplierLinkRead]
    total: int
    limit: int
    offset: int
