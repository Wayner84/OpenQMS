"""Suppliers endpoints: approved-supplier records, certifications, and performance
history.

Per docs/API.md and the Milestone 3 plan's design decision 2: every operation here
requires only authentication (any active user), not admin privilege -- Suppliers is
collaborative reference data, matching the People module's precedent, not
Document Management's admin-gated categories/tags. Every guard is still fully
re-enforced server-side and scoped to `current_user.organisation_id`, never a
client-supplied value.

Route ordering note: `GET /suppliers/certifications/expiring` is registered before
`GET /suppliers/{supplier_id}` so FastAPI's first-match routing doesn't try to parse
the literal segment "certifications" as a `supplier_id` UUID path parameter.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser
from app.modules.ncr.schemas import NcrListResponse, NcrRead
from app.modules.ncr.service import list_ncrs
from app.modules.suppliers.models import ApprovalStatus, RiskRating
from app.modules.suppliers.schemas import (
    SupplierCertificationListResponse,
    SupplierCertificationRead,
    SupplierCertificationWriteRequest,
    SupplierListResponse,
    SupplierPerformanceRecordListResponse,
    SupplierPerformanceRecordRead,
    SupplierPerformanceRecordWriteRequest,
    SupplierRead,
    SupplierWriteRequest,
)
from app.modules.suppliers.service import (
    CertificateDocumentNotFoundError,
    SupplierCertificationNotFoundError,
    SupplierCompanyNotFoundError,
    SupplierNotFoundError,
    create_certification,
    create_performance_record,
    create_supplier,
    delete_certification,
    delete_supplier,
    get_supplier,
    list_certifications,
    list_expiring_certifications,
    list_performance_records,
    list_suppliers,
    update_certification,
    update_supplier,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


# --- Suppliers -----------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_supplier_endpoint(
    payload: SupplierWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> SupplierRead:
    try:
        supplier = await create_supplier(
            session,
            organisation_id=current_user.organisation_id,
            company_id=payload.company_id,
            approval_status=payload.approval_status,
            risk_rating=payload.risk_rating,
            is_preferred=payload.is_preferred,
            notes=payload.notes,
            created_by_id=current_user.id,
        )
    except SupplierCompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return SupplierRead.model_validate(supplier)


@router.get("")
async def list_suppliers_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    approval_status: ApprovalStatus | None = None,
    risk_rating: RiskRating | None = None,
    is_preferred: bool | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplierListResponse:
    suppliers, total = await list_suppliers(
        session,
        organisation_id=current_user.organisation_id,
        approval_status=approval_status,
        risk_rating=risk_rating,
        is_preferred=is_preferred,
        search=search,
        limit=limit,
        offset=offset,
    )
    return SupplierListResponse(
        items=[SupplierRead.model_validate(s) for s in suppliers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/certifications/expiring")
async def list_expiring_certifications_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    within_days: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplierCertificationListResponse:
    """Certifications expiring within `within_days` (or the organisation's
    configured reminder window if not given), soonest first. Read-only -- see the
    Milestone 3 plan's design decision 5."""
    certifications, total = await list_expiring_certifications(
        session,
        organisation_id=current_user.organisation_id,
        within_days=within_days,
        limit=limit,
        offset=offset,
    )
    return SupplierCertificationListResponse(
        items=[SupplierCertificationRead.model_validate(c) for c in certifications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{supplier_id}")
async def get_supplier_endpoint(
    supplier_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> SupplierRead:
    try:
        supplier = await get_supplier(
            session, organisation_id=current_user.organisation_id, supplier_id=supplier_id
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    return SupplierRead.model_validate(supplier)


@router.patch("/{supplier_id}")
async def update_supplier_endpoint(
    supplier_id: uuid.UUID,
    payload: SupplierWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> SupplierRead:
    try:
        supplier = await update_supplier(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            updated_by_id=current_user.id,
            company_id=payload.company_id,
            approval_status=payload.approval_status,
            risk_rating=payload.risk_rating,
            is_preferred=payload.is_preferred,
            notes=payload.notes,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except SupplierCompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return SupplierRead.model_validate(supplier)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier_endpoint(
    supplier_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    try:
        await delete_supplier(
            session, organisation_id=current_user.organisation_id, supplier_id=supplier_id
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc


# --- Certifications --------------------------------------------------------------


@router.post("/{supplier_id}/certifications", status_code=status.HTTP_201_CREATED)
async def create_certification_endpoint(
    supplier_id: uuid.UUID,
    payload: SupplierCertificationWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> SupplierCertificationRead:
    try:
        certification = await create_certification(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            certification_type=payload.certification_type,
            certificate_document_id=payload.certificate_document_id,
            issued_date=payload.issued_date,
            expiry_date=payload.expiry_date,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    except CertificateDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return SupplierCertificationRead.model_validate(certification)


@router.get("/{supplier_id}/certifications")
async def list_certifications_endpoint(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplierCertificationListResponse:
    try:
        certifications, total = await list_certifications(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            limit=limit,
            offset=offset,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    return SupplierCertificationListResponse(
        items=[SupplierCertificationRead.model_validate(c) for c in certifications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{supplier_id}/certifications/{certification_id}")
async def update_certification_endpoint(
    supplier_id: uuid.UUID,
    certification_id: uuid.UUID,
    payload: SupplierCertificationWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> SupplierCertificationRead:
    try:
        certification = await update_certification(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            certification_id=certification_id,
            certification_type=payload.certification_type,
            certificate_document_id=payload.certificate_document_id,
            issued_date=payload.issued_date,
            expiry_date=payload.expiry_date,
        )
    except (SupplierNotFoundError, SupplierCertificationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found"
        ) from exc
    except CertificateDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return SupplierCertificationRead.model_validate(certification)


@router.delete(
    "/{supplier_id}/certifications/{certification_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_certification_endpoint(
    supplier_id: uuid.UUID,
    certification_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
) -> None:
    try:
        await delete_certification(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            certification_id=certification_id,
        )
    except (SupplierNotFoundError, SupplierCertificationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certification not found"
        ) from exc


# --- Performance records ----------------------------------------------------------


@router.post("/{supplier_id}/performance", status_code=status.HTTP_201_CREATED)
async def create_performance_record_endpoint(
    supplier_id: uuid.UUID,
    payload: SupplierPerformanceRecordWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> SupplierPerformanceRecordRead:
    try:
        record = await create_performance_record(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            period=payload.period,
            score=payload.score,
            notes=payload.notes,
            created_by_id=current_user.id,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    return SupplierPerformanceRecordRead.model_validate(record)


@router.get("/{supplier_id}/performance")
async def list_performance_records_endpoint(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SupplierPerformanceRecordListResponse:
    try:
        records, total = await list_performance_records(
            session,
            organisation_id=current_user.organisation_id,
            supplier_id=supplier_id,
            limit=limit,
            offset=offset,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc
    return SupplierPerformanceRecordListResponse(
        items=[SupplierPerformanceRecordRead.model_validate(r) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


# --- NCR history -----------------------------------------------------------------


@router.get("/{supplier_id}/ncr-history")
async def list_supplier_ncr_history_endpoint(
    supplier_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NcrListResponse:
    """Read-only, per the Milestone 3 plan's design decision 6 (deferred here
    until the NCR schema existed) and the Milestone 4 plan's design decision 9.
    Reuses `ncr.service.list_ncrs`'s own `supplier_id` filter -- the owning
    module's public service function, per the module-isolation rule -- rather
    than querying `ncrs` directly."""
    try:
        await get_supplier(
            session, organisation_id=current_user.organisation_id, supplier_id=supplier_id
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        ) from exc

    ncrs, total = await list_ncrs(
        session,
        organisation_id=current_user.organisation_id,
        type=None,
        status=None,
        product_id=None,
        supplier_id=supplier_id,
        raised_by_id=None,
        search=None,
        limit=limit,
        offset=offset,
    )
    return NcrListResponse(
        items=[NcrRead.model_validate(n) for n in ncrs], total=total, limit=limit, offset=offset
    )
