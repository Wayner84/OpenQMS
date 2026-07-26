"""add document approvals

Revision ID: ea4516740593
Revises: 8dc9425047ca
Create Date: 2026-07-26 13:55:39.497702

Milestone 2 (Document Management) approval workflow, per
.hermes/plans/2026-07-26-milestone-2-document-management.md#5-workflow-state-machine:
an immutable, actor-and-timestamp-stamped record of every approve/reject decision.
`approver_id` references `users.id`, not `people.id` -- see
docs/DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table
for why.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea4516740593"
down_revision: str | None = "8dc9425047ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=False),
        sa.Column(
            "decision",
            sa.Enum("approved", "rejected", name="document_approval_decision"),
            nullable=False,
        ),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("document_approvals")
    op.execute(sa.text("DROP TYPE IF EXISTS document_approval_decision"))
