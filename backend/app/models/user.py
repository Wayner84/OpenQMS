"""The `users` table: authenticated accounts scoped to one organisation, per the
Milestone 1 plan (.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md).
"""

import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRole(str, enum.Enum):
    """Fixed roles for Milestone 1, per docs/Database.md#naming-conventions."""

    ADMIN = "admin"
    MEMBER = "member"


class User(Base):
    """An authenticated account belonging to exactly one organisation.

    `token_version` implements the logout/revocation strategy recorded in
    DecisionLog: incrementing it invalidates every JWT issued before the increment,
    since `get_current_user` rejects a token whose `ver` claim doesn't match.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organisation_id", "email", name="uq_users_org_email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
