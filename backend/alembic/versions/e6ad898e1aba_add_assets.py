"""add assets

Revision ID: e6ad898e1aba
Revises: 5fe9edf6d2c5
Create Date: 2026-08-01 12:00:00.000000

Milestone 5 (Calibration and Asset Management) schema slice 1, per
.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md#1-schema:
inspection/measuring equipment and company asset records. Soft-deletes
(`deleted_at`), matching `documents`/`ncrs`' precedent -- an asset carries
audit-significant calibration history (added in a later slice), unlike
Products/Suppliers' hard-deletable pure reference data (plan design decision 9).

Also seeds one `configuration` row (docs/Database.md#configuration-table) for the
existing default organisation: `calibration_due_reminder_window_days`, mirroring
`supplier_certification_reminder_window_days`'s existing precedent (plan design
decision 7). The value is inlined here, not imported from application code, so
this migration's historical behaviour never changes if a future session edits the
application's own fallback default.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6ad898e1aba"
down_revision: str | None = "5fe9edf6d2c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMINDER_WINDOW_KEY = "calibration_due_reminder_window_days"
DEFAULT_REMINDER_WINDOW = {"days": 30}


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("asset_tag", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(
                "measuring_equipment",
                "inspection_equipment",
                "company_asset",
                name="asset_type",
            ),
            nullable=False,
        ),
        sa.Column("serial_number", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("in_service", "out_of_service", "retired", name="asset_status"),
            nullable=False,
        ),
        sa.Column("purchase_date", sa.Date(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "asset_tag", name="uq_assets_org_asset_tag"),
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
    op.drop_table("assets")
    op.execute(sa.text("DROP TYPE IF EXISTS asset_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS asset_type"))
