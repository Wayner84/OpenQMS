"""add document acknowledgements

Revision ID: b8a145cc3e28
Revises: ea4516740593
Create Date: 2026-07-26 14:21:45.542242

Milestone 2 (Document Management) electronic acknowledgement, per
.hermes/plans/2026-07-26-milestone-2-document-management.md: an immutable "I have
read and understood this document" record. `acknowledged_by_id` references
`users.id`, not `people.id` -- same reasoning as `document_approvals.approver_id`;
see
docs/DecisionLog.md#2026-07-26-document-management-schema-numbering-and-the-deferred-audit_log-table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8a145cc3e28"
down_revision: str | None = "ea4516740593"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_acknowledgements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("acknowledged_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["acknowledged_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id",
            "acknowledged_by_id",
            name="uq_document_acknowledgements_version_user",
        ),
    )


def downgrade() -> None:
    op.drop_table("document_acknowledgements")
