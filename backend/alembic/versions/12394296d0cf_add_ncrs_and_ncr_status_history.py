"""add ncrs and ncr_status_history

Revision ID: 12394296d0cf
Revises: a6c2d94f7e13
Create Date: 2026-07-29 12:00:00.000000

Milestone 4 (NCR) schema slice 1, per
.hermes/plans/2026-07-29-milestone-4-ncr.md#1-schema: non-conformance reports and
their immutable workflow-transition history.

The `ncr_status` enum is created once explicitly (checkfirst=True) and referenced
with `create_type=False` by all three columns that use it (`ncrs.status`,
`ncr_status_history.from_status`, `ncr_status_history.to_status`) -- reusing one
Postgres enum type across columns in hand-written `op.create_table` calls (unlike
`Base.metadata.create_all`, which dedupes automatically) requires exactly this
create-once-then-reference pattern, or the second column's implicit `CREATE TYPE`
fails with "type already exists".

Also seeds one `configuration` row (docs/Database.md#configuration-table) for the
existing default organisation: `ncr_numbering_scheme`, holding both the internal
(`NCR`) and supplier (`SNCR`) prefixes/sequences in one row (plan design decision
6), mirroring the pattern already used for `document_numbering_scheme` in
8dc9425047ca and `supplier_certification_reminder_window_days` in d47b9e2c1a05. The
value is inlined here, not imported from application code, so this migration's
historical behaviour never changes if a future session edits the application's own
fallback default.

`ncrs` also carries `UniqueConstraint(organisation_id, number)`, matching
`documents`' `uq_documents_org_number` (8dc9425047ca) -- a DB-level backstop
alongside the `SELECT ... FOR UPDATE` numbering lock, per an independent security
review's finding that this slice was missing the belt-and-braces uniqueness
convention used everywhere else server-generated numbers exist in this codebase.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12394296d0cf"
down_revision: str | None = "a6c2d94f7e13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NUMBERING_SCHEME_KEY = "ncr_numbering_scheme"
DEFAULT_NUMBERING_SCHEME = {
    "internal": {"prefix": "NCR", "separator": "-", "padding": 4, "next_sequence": 1},
    "supplier": {"prefix": "SNCR", "separator": "-", "padding": 4, "next_sequence": 1},
}

NCR_STATUS_VALUES = (
    "open",
    "investigate",
    "containment",
    "corrective_action",
    "verification",
    "closed",
)


def upgrade() -> None:
    ncr_status_enum = postgresql.ENUM(*NCR_STATUS_VALUES, name="ncr_status")
    ncr_status_enum.create(op.get_bind(), checkfirst=True)
    ncr_status_column_type = postgresql.ENUM(
        *NCR_STATUS_VALUES, name="ncr_status", create_type=False
    )

    op.create_table(
        "ncrs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(), nullable=False),
        sa.Column("type", sa.Enum("internal", "supplier", name="ncr_type"), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
        sa.Column("status", ncr_status_column_type, nullable=False),
        sa.Column("raised_by_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("root_cause_summary", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=False),
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
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["raised_by_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_ncrs_org_number"),
    )
    op.create_table(
        "ncr_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncr_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", ncr_status_column_type, nullable=True),
        sa.Column("to_status", ncr_status_column_type, nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ncr_id"], ["ncrs.id"], ondelete="CASCADE"),
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
                key=NUMBERING_SCHEME_KEY,
                value=DEFAULT_NUMBERING_SCHEME,
            )
            .on_conflict_do_nothing(index_elements=["organisation_id", "key"])
        )


def downgrade() -> None:
    op.drop_table("ncr_status_history")
    op.drop_table("ncrs")
    op.execute(sa.text("DROP TYPE IF EXISTS ncr_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS ncr_type"))
