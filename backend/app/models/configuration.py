"""The `configuration` table: database-driven business configuration scoped to an
organisation, per docs/Database.md#configuration-table. Proves the cross-cutting
"no hard-coded business rules" pattern end to end; individual modules add their own
typed rows using the same (organisation_id, key) -> value shape.
"""

import datetime
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# JSONB on PostgreSQL (production/Docker); plain JSON on SQLite (fast unit tests only),
# per docs/Database.md#engines.
JsonValue = JSONB().with_variant(JSON(), "sqlite")


class Configuration(Base):
    """One organisation-scoped, data-driven configuration value."""

    __tablename__ = "configuration"
    __table_args__ = (UniqueConstraint("organisation_id", "key", name="uq_configuration_org_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JsonValue, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
