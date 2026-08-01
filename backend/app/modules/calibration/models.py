"""SQLAlchemy models for the Calibration and Asset Management module: assets and
(in later slices) their calibration schedules/events and maintenance schedules. Per
docs/modules/CalibrationAndAssetManagement.md and the Milestone 5 plan
(.hermes/plans/2026-08-01-milestone-5-calibration-and-asset-management.md).

`owner_id` references `people.id` (an organisational assignment -- who is
responsible for the asset -- that can validly name someone without a login,
matching `ncrs.raised_by_id`/`ncr_actions.owner_id`'s precedent).
"""

import datetime
import enum
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssetType(str, enum.Enum):
    """Fixed set of tracked-equipment types, per docs/Database.md#naming-conventions."""

    MEASURING_EQUIPMENT = "measuring_equipment"
    INSPECTION_EQUIPMENT = "inspection_equipment"
    COMPANY_ASSET = "company_asset"


class AssetStatus(str, enum.Enum):
    """An asset's current operational state."""

    IN_SERVICE = "in_service"
    OUT_OF_SERVICE = "out_of_service"
    RETIRED = "retired"


def _calibration_enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda cls: [member.value for member in cls],
    )


class Asset(Base):
    """Inspection/measuring equipment or a company asset. `asset_tag` is the
    physical label an operator reads off the equipment, unique per organisation
    (design decision 8) -- enforced at the service layer with a clean `409`, not
    solely by the DB constraint, matching `products.part_number`'s precedent.
    Soft-deletes (design decision 9): an asset carries audit-significant
    calibration history, like `documents`/`ncrs`, unlike Products/Suppliers'
    hard-deletable pure reference data."""

    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("organisation_id", "asset_tag", name="uq_assets_org_asset_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"), nullable=False
    )
    asset_tag: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        _calibration_enum_column(AssetType, "asset_type"), nullable=False
    )
    serial_number: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    status: Mapped[AssetStatus] = mapped_column(
        _calibration_enum_column(AssetStatus, "asset_status"),
        nullable=False,
        default=AssetStatus.IN_SERVICE,
    )
    purchase_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
