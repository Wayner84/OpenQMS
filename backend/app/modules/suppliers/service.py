"""Business logic for the Suppliers module: approved-supplier records,
certifications, and performance history. Per docs/modules/Suppliers.md and the
Milestone 3 plan (.hermes/plans/2026-07-28-milestone-3-products-and-suppliers.md):
every operation is scoped to the caller's organisation; `company_id` is validated
against the People module's own service and `certificate_document_id` against the
Document Management module's own service (module boundary rule -- see
docs/CodingStandards.md#backend-python), never queried directly.
"""

import datetime
import decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.service import DocumentNotFoundError, get_document
from app.modules.people.service import (
    CompanyNotFoundError,
    get_company,
    list_company_ids_matching_name,
)
from app.modules.suppliers.models import (
    ApprovalStatus,
    RiskRating,
    Supplier,
    SupplierCertification,
    SupplierPerformanceRecord,
)
from app.modules.suppliers.reminder_config import get_reminder_window_days


class SupplierNotFoundError(Exception):
    """Raised when a supplier id doesn't exist in the caller's organisation."""


class SupplierCompanyNotFoundError(Exception):
    """Raised when a supplier's `company_id` doesn't exist (as a company) in the
    caller's organisation."""


class SupplierCertificationNotFoundError(Exception):
    """Raised when a certification id doesn't exist for the given supplier (which
    is itself already scoped to the caller's organisation)."""


class CertificateDocumentNotFoundError(Exception):
    """Raised when a certification's `certificate_document_id` doesn't exist (as a
    document) in the caller's organisation."""


async def _validate_company(
    session: AsyncSession, *, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    try:
        await get_company(session, organisation_id=organisation_id, company_id=company_id)
    except CompanyNotFoundError as exc:
        raise SupplierCompanyNotFoundError(str(exc)) from exc


async def _validate_certificate_document(
    session: AsyncSession, *, organisation_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    try:
        await get_document(session, organisation_id=organisation_id, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise CertificateDocumentNotFoundError(str(exc)) from exc


# --- Suppliers ----------------------------------------------------------------


async def create_supplier(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    approval_status: ApprovalStatus,
    risk_rating: RiskRating | None,
    is_preferred: bool,
    notes: str | None,
    created_by_id: uuid.UUID | None,
) -> Supplier:
    await _validate_company(session, organisation_id=organisation_id, company_id=company_id)

    supplier = Supplier(
        organisation_id=organisation_id,
        company_id=company_id,
        approval_status=approval_status,
        risk_rating=risk_rating,
        is_preferred=is_preferred,
        notes=notes,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def get_supplier(
    session: AsyncSession, *, organisation_id: uuid.UUID, supplier_id: uuid.UUID
) -> Supplier:
    supplier = (
        await session.execute(
            select(Supplier).where(
                Supplier.id == supplier_id, Supplier.organisation_id == organisation_id
            )
        )
    ).scalar_one_or_none()
    if supplier is None:
        raise SupplierNotFoundError(f"No supplier {supplier_id} in this organisation")
    return supplier


async def list_suppliers(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    approval_status: ApprovalStatus | None,
    risk_rating: RiskRating | None,
    is_preferred: bool | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Supplier], int]:
    """List suppliers, optionally filtered by exact `approval_status`/`risk_rating`/
    `is_preferred`, and a case-insensitive substring `search` across the linked
    company's name (resolved via the People module's own service, per the
    module-isolation rule -- see `list_company_ids_matching_name`)."""
    filters = [Supplier.organisation_id == organisation_id]
    if approval_status is not None:
        filters.append(Supplier.approval_status == approval_status)
    if risk_rating is not None:
        filters.append(Supplier.risk_rating == risk_rating)
    if is_preferred is not None:
        filters.append(Supplier.is_preferred == is_preferred)
    if search:
        matching_company_ids = await list_company_ids_matching_name(
            session, organisation_id=organisation_id, search=search
        )
        filters.append(Supplier.company_id.in_(matching_company_ids))

    total = (
        await session.execute(select(func.count()).select_from(Supplier).where(*filters))
    ).scalar_one()

    result = await session.execute(
        select(Supplier).where(*filters).order_by(Supplier.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_supplier(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    updated_by_id: uuid.UUID | None,
    company_id: uuid.UUID,
    approval_status: ApprovalStatus,
    risk_rating: RiskRating | None,
    is_preferred: bool,
    notes: str | None,
) -> Supplier:
    supplier = await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
    await _validate_company(session, organisation_id=organisation_id, company_id=company_id)

    supplier.company_id = company_id
    supplier.approval_status = approval_status
    supplier.risk_rating = risk_rating
    supplier.is_preferred = is_preferred
    supplier.notes = notes
    supplier.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def delete_supplier(
    session: AsyncSession, *, organisation_id: uuid.UUID, supplier_id: uuid.UUID
) -> None:
    """Hard delete: certifications/performance records cascade at the DB level (`ON
    DELETE CASCADE` -- see the migration), since they are wholly owned by the
    supplier, not independently referenced elsewhere."""
    supplier = await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
    await session.delete(supplier)
    await session.commit()


# --- Certifications -------------------------------------------------------------


async def create_certification(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    certification_type: str,
    certificate_document_id: uuid.UUID | None,
    issued_date: datetime.date | None,
    expiry_date: datetime.date | None,
) -> SupplierCertification:
    await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
    if certificate_document_id is not None:
        await _validate_certificate_document(
            session, organisation_id=organisation_id, document_id=certificate_document_id
        )

    certification = SupplierCertification(
        supplier_id=supplier_id,
        certification_type=certification_type,
        certificate_document_id=certificate_document_id,
        issued_date=issued_date,
        expiry_date=expiry_date,
    )
    session.add(certification)
    await session.commit()
    await session.refresh(certification)
    return certification


async def get_certification(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    certification_id: uuid.UUID,
) -> SupplierCertification:
    await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)
    certification = (
        await session.execute(
            select(SupplierCertification).where(
                SupplierCertification.id == certification_id,
                SupplierCertification.supplier_id == supplier_id,
            )
        )
    ).scalar_one_or_none()
    if certification is None:
        raise SupplierCertificationNotFoundError(
            f"No certification {certification_id} for supplier {supplier_id}"
        )
    return certification


async def list_certifications(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SupplierCertification], int]:
    await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(SupplierCertification)
            .where(SupplierCertification.supplier_id == supplier_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(SupplierCertification)
        .where(SupplierCertification.supplier_id == supplier_id)
        .order_by(SupplierCertification.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_certification(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    certification_id: uuid.UUID,
    certification_type: str,
    certificate_document_id: uuid.UUID | None,
    issued_date: datetime.date | None,
    expiry_date: datetime.date | None,
) -> SupplierCertification:
    certification = await get_certification(
        session,
        organisation_id=organisation_id,
        supplier_id=supplier_id,
        certification_id=certification_id,
    )
    if certificate_document_id is not None:
        await _validate_certificate_document(
            session, organisation_id=organisation_id, document_id=certificate_document_id
        )

    certification.certification_type = certification_type
    certification.certificate_document_id = certificate_document_id
    certification.issued_date = issued_date
    certification.expiry_date = expiry_date
    await session.commit()
    await session.refresh(certification)
    return certification


async def delete_certification(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    certification_id: uuid.UUID,
) -> None:
    certification = await get_certification(
        session,
        organisation_id=organisation_id,
        supplier_id=supplier_id,
        certification_id=certification_id,
    )
    await session.delete(certification)
    await session.commit()


async def list_expiring_certifications(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    within_days: int | None,
    limit: int,
    offset: int,
) -> tuple[list[SupplierCertification], int]:
    """Certifications expiring within `within_days` (or the organisation's
    configured reminder window if not given), soonest first. Read-only -- see the
    Milestone 3 plan's design decision 5 for why this doesn't send anything."""
    window_days = (
        within_days
        if within_days is not None
        else await get_reminder_window_days(session, organisation_id=organisation_id)
    )
    cutoff = datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=window_days)

    filters = [
        Supplier.organisation_id == organisation_id,
        SupplierCertification.expiry_date.is_not(None),
        SupplierCertification.expiry_date <= cutoff,
    ]
    total = (
        await session.execute(
            select(func.count())
            .select_from(SupplierCertification)
            .join(Supplier, Supplier.id == SupplierCertification.supplier_id)
            .where(*filters)
        )
    ).scalar_one()
    result = await session.execute(
        select(SupplierCertification)
        .join(Supplier, Supplier.id == SupplierCertification.supplier_id)
        .where(*filters)
        .order_by(SupplierCertification.expiry_date)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


# --- Performance records --------------------------------------------------------


async def create_performance_record(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    period: str,
    score: decimal.Decimal,
    notes: str | None,
    created_by_id: uuid.UUID | None,
) -> SupplierPerformanceRecord:
    await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)

    record = SupplierPerformanceRecord(
        supplier_id=supplier_id,
        period=period,
        score=score,
        notes=notes,
        created_by_id=created_by_id,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_performance_records(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    supplier_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[SupplierPerformanceRecord], int]:
    await get_supplier(session, organisation_id=organisation_id, supplier_id=supplier_id)

    total = (
        await session.execute(
            select(func.count())
            .select_from(SupplierPerformanceRecord)
            .where(SupplierPerformanceRecord.supplier_id == supplier_id)
        )
    ).scalar_one()
    result = await session.execute(
        select(SupplierPerformanceRecord)
        .where(SupplierPerformanceRecord.supplier_id == supplier_id)
        .order_by(SupplierPerformanceRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total
