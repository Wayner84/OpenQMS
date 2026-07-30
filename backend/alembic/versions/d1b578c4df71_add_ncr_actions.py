"""add ncr_actions

Revision ID: d1b578c4df71
Revises: 12394296d0cf
Create Date: 2026-07-30 09:00:00.000000

Milestone 4 (NCR) schema slice 2, per
.hermes/plans/2026-07-29-milestone-4-ncr.md#1-schema: containment/corrective/
preventive actions tracked against an NCR, with owners and due dates. An NCR
cannot transition to `closed` while any of its actions are still `open` (design
decision 4) -- that guard is enforced in the service layer against this table, not
by a DB constraint (a cross-table conditional check isn't expressible as one).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1b578c4df71"
down_revision: str | None = "12394296d0cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ncr_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncr_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("open", "complete", name="ncr_action_status"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["owner_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ncr_actions")
    op.execute(sa.text("DROP TYPE IF EXISTS ncr_action_status"))
