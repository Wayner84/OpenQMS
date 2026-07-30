"""add ncr_investigation_tools

Revision ID: 2df37403d75c
Revises: d1b578c4df71
Create Date: 2026-07-30 11:00:00.000000

Milestone 4 (NCR) schema slice 3, per
.hermes/plans/2026-07-29-milestone-4-ncr.md#1-schema: structured investigation
aids (5 Why, Fishbone, 8D, 10D), one evolving worksheet per (ncr_id, tool_type),
upserted via PUT rather than a separate create/update distinction (design
decision 7).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2df37403d75c"
down_revision: str | None = "d1b578c4df71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ncr_investigation_tools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncr_id", sa.Uuid(), nullable=False),
        sa.Column(
            "tool_type",
            postgresql.ENUM(
                "five_why",
                "fishbone",
                "eight_d",
                "ten_d",
                name="ncr_investigation_tool_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ncr_id"], ["ncrs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ncr_id", "tool_type", name="uq_ncr_investigation_tools_ncr_tool_type"),
    )


def downgrade() -> None:
    op.drop_table("ncr_investigation_tools")
    op.execute(sa.text("DROP TYPE IF EXISTS ncr_investigation_tool_type"))
