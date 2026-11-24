"""add calibration_schedules and calibration_events

Revision ID: 4bac6c2e8f04
Revises: e6ad898e1aba
Create Date: 2026-08-01 14:00:00.000000

Milestone 5 (Calibration and Asset Management) schema slice 2, per
.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md#1-schema:
an asset's calibration interval/due date (one row per asset) and its immutable
calibration event history.

The `calibration_interval_unit` enum is created once explicitly
(`checkfirst=True`) and referenced with `create_type=False`, following the same
create-once-then-reference pattern used elsewhere in this codebase for a
Postgres enum reused across more than one hand-written `op.create_table` call
(see e.g. `ncr_status` in 12394296d0cf) -- only `calibration_schedules.interval_unit`
uses it in this migration, but `asset_maintenance_schedules` (a later slice) will
reuse this exact same type, so it's created via the reusable pattern from the
start rather than inline.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4bac6c2e8f04"
down_revision: str | None = "e6ad898e1aba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTERVAL_UNIT_VALUES = ("days", "months", "years")


def upgrade() -> None:
    interval_unit_enum = postgresql.ENUM(*INTERVAL_UNIT_VALUES, name="calibration_interval_unit")
    interval_unit_enum.create(op.get_bind(), checkfirst=True)
    interval_unit_column_type = postgresql.ENUM(
        *INTERVAL_UNIT_VALUES, name="calibration_interval_unit", create_type=False
    )

    op.create_table(
        "calibration_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("interval_value", sa.Integer(), nullable=False),
        sa.Column("interval_unit", interval_unit_column_type, nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", name="uq_calibration_schedules_asset_id"),
    )
    op.create_table(
        "calibration_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("performed_at", sa.Date(), nullable=False),
        sa.Column("performed_by_id", sa.Uuid(), nullable=True),
        sa.Column("performed_by_supplier_id", sa.Uuid(), nullable=True),
        sa.Column("certificate_document_id", sa.Uuid(), nullable=True),
        sa.Column(
            "result",
            sa.Enum("pass", "fail", "limited", name="calibration_result"),
            nullable=False,
        ),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["certificate_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["performed_by_id"], ["people.id"]),
        sa.ForeignKeyConstraint(["performed_by_supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("calibration_events")
    op.drop_table("calibration_schedules")
    op.execute(sa.text("DROP TYPE IF EXISTS calibration_result"))
    op.execute(sa.text("DROP TYPE IF EXISTS calibration_interval_unit"))
