"""Add asset maintenance schedules.

Revision ID: 2026f00d1a21
Revises: 4bac6c2e8f04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2026f00d1a21"
down_revision: str | None = "4bac6c2e8f04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_maintenance_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("interval_value", sa.Integer(), nullable=False),
        sa.Column(
            "interval_unit",
            postgresql.ENUM(
                "days", "months", "years", name="calibration_interval_unit", create_type=False
            ),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "interval_value > 0", name="ck_asset_maintenance_schedules_positive_interval"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", name="uq_asset_maintenance_schedules_asset_id"),
    )


def downgrade() -> None:
    op.drop_table("asset_maintenance_schedules")
