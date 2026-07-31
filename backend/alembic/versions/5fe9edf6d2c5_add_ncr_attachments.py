"""add ncr_attachments

Revision ID: 5fe9edf6d2c5
Revises: 2df37403d75c
Create Date: 2026-07-30 13:00:00.000000

Milestone 4 (NCR) schema slice 4, per
.hermes/plans/2026-07-29-milestone-4-ncr.md#1-schema: Document Management records
attached as supporting evidence for an NCR. `UniqueConstraint(ncr_id, document_id)`
-- attaching the same document twice is a clean 409, not a raw IntegrityError,
matching the Products link-table precedent.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5fe9edf6d2c5"
down_revision: str | None = "2df37403d75c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ncr_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncr_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["ncr_id"], ["ncrs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ncr_id", "document_id", name="uq_ncr_attachments_ncr_document"),
    )


def downgrade() -> None:
    op.drop_table("ncr_attachments")
