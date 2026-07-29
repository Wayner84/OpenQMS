"""add suppliers, supplier_certifications, and supplier_performance_records

Revision ID: d47b9e2c1a05
Revises: b8a145cc3e28
Create Date: 2026-07-29 09:00:00.000000

Milestone 3 (Products and Suppliers) schema slice 1, per
.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md#1-suppliers-schema:
approved-supplier records wrapping a People `companies` row, their certifications
(with an optional link to a Document Management `documents` row), and append-only
performance history.

`risk_rating` and `supplier_performance_records.score` are plain operator-entered
values (design decisions 3-4 in the plan) -- no scoring formula is implemented here.

Also seeds one `configuration` row (docs/Database.md#configuration-table) for the
existing default organisation: `supplier_certification_reminder_window_days`
(consumed by app/modules/suppliers/reminder_config.py), mirroring the pattern
already used for `document_numbering_scheme`/`document_upload_policy` in
8dc9425047ca. The value is inlined here, not imported from application code, so this
migration's historical behaviour never changes if a future session edits the
application's own fallback default.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d47b9e2c1a05"
down_revision: str | None = "b8a145cc3e28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMINDER_WINDOW_KEY = "supplier_certification_reminder_window_days"
DEFAULT_REMINDER_WINDOW = {"days": 30}


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "approval_status",
            sa.Enum("approved", "pending", "suspended", name="supplier_approval_status"),
            nullable=False,
        ),
        sa.Column(
            "risk_rating",
            sa.Enum("low", "medium", "high", name="supplier_risk_rating"),
            nullable=True,
        ),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "supplier_certifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("certification_type", sa.String(), nullable=False),
        sa.Column("certificate_document_id", sa.Uuid(), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["certificate_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "supplier_performance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    organisations_table = sa.table(
        "organisations", sa.column("id", sa.Uuid()), sa.column("slug", sa.String())
    )
    configuration_table = sa.table(
        "configuration",
        sa.column("id", sa.Uuid()),
        sa.column("organisation_id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("value", postgresql.JSONB(astext_type=sa.Text())),
    )

    connection = op.get_bind()
    default_organisation_id = connection.execute(
        sa.select(organisations_table.c.id).where(organisations_table.c.slug == "default")
    ).scalar_one_or_none()

    if default_organisation_id is not None:
        op.execute(
            pg_insert(configuration_table)
            .values(
                id=uuid.uuid4(),
                organisation_id=default_organisation_id,
                key=REMINDER_WINDOW_KEY,
                value=DEFAULT_REMINDER_WINDOW,
            )
            .on_conflict_do_nothing(index_elements=["organisation_id", "key"])
        )


def downgrade() -> None:
    op.drop_table("supplier_performance_records")
    op.drop_table("supplier_certifications")
    op.drop_table("suppliers")
    op.execute(sa.text("DROP TYPE IF EXISTS supplier_risk_rating"))
    op.execute(sa.text("DROP TYPE IF EXISTS supplier_approval_status"))
