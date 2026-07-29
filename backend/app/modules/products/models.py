"""SQLAlchemy models for the Products module: product categories, product records,
and their links to Document Management drawings/specs and Suppliers. Per
docs/modules/Products.md and the Milestone 3 plan
(.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md).
"""

import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductType(str, enum.Enum):
    """Fixed set of product types, per docs/Database.md#naming-conventions."""

    INTERNAL = "internal"
    PURCHASED = "purchased"
    ASSEMBLY = "assembly"
    COMPONENT = "component"


class ProductDocumentRelationshipType(str, enum.Enum):
    """How a linked Document Management record relates to a product."""

    DRAWING = "drawing"
    SPECIFICATION = "specification"
    CAD = "cad"


class ProductCategory(Base):
    """A flat (non-hierarchical) product category -- unlike Document Management's
    tree-shaped categories, per the module doc's planned-tables section."""

    __tablename__ = "product_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Product(Base):
    """A product/component record: part number, description, revision, category,
    type, and manufacturing notes. `part_number` is unique per organisation,
    enforced at the service layer (a clean `409`, matching `document_tags.name`'s
    existing precedent), not solely by the DB constraint."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organisation_id", "part_number", name="uq_products_org_part_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    part_number: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[str] = mapped_column(String, nullable=False, default="A")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id"), nullable=True
    )
    type: Mapped[ProductType] = mapped_column(
        Enum(
            ProductType,
            name="product_type",
            native_enum=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    manufacturing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProductDocument(Base):
    """A link from a product to a Document Management record (drawing/spec/CAD).
    The same document may be linked under more than one relationship type, but not
    twice under the identical type."""

    __tablename__ = "product_documents"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "document_id",
            "relationship_type",
            name="uq_product_documents_product_document_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    relationship_type: Mapped[ProductDocumentRelationshipType] = mapped_column(
        Enum(
            ProductDocumentRelationshipType,
            name="product_document_relationship_type",
            native_enum=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductSupplierLink(Base):
    """A link from a product to an approved supplier that can provide it."""

    __tablename__ = "product_supplier_links"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "supplier_id", name="uq_product_supplier_links_product_supplier"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
