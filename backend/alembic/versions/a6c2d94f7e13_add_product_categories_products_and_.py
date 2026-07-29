"""add product_categories, products, product_documents, and product_supplier_links

Revision ID: a6c2d94f7e13
Revises: d47b9e2c1a05
Create Date: 2026-07-29 11:00:00.000000

Milestone 3 (Products and Suppliers) schema slice 2, per
.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md#2-products-schema:
flat (non-hierarchical) product categories, product/component records, and their
links to Document Management drawings/specs and Suppliers -- both of which already
exist by this point in the migration chain.

`part_number` carries a DB-level `UniqueConstraint(organisation_id, part_number)` as
a defence-in-depth backstop, but the clean `409` on conflict is enforced at the
service layer (see app/modules/products/service.py), matching
`document_tags.name`'s existing precedent.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6c2d94f7e13"
down_revision: str | None = "d47b9e2c1a05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("part_number", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column(
            "type",
            sa.Enum("internal", "purchased", "assembly", "component", name="product_type"),
            nullable=False,
        ),
        sa.Column("manufacturing_notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "part_number", name="uq_products_org_part_number"),
    )
    op.create_table(
        "product_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "relationship_type",
            sa.Enum("drawing", "specification", "cad", name="product_document_relationship_type"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "document_id",
            "relationship_type",
            name="uq_product_documents_product_document_type",
        ),
    )
    op.create_table(
        "product_supplier_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "supplier_id", name="uq_product_supplier_links_product_supplier"
        ),
    )


def downgrade() -> None:
    op.drop_table("product_supplier_links")
    op.drop_table("product_documents")
    op.drop_table("products")
    op.drop_table("product_categories")
    op.execute(sa.text("DROP TYPE IF EXISTS product_document_relationship_type"))
    op.execute(sa.text("DROP TYPE IF EXISTS product_type"))
