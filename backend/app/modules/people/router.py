"""People module endpoints: companies and people (employees/contacts).

Per docs/modules/People.md and docs/API.md. Every operation requires authentication
(any active user in the organisation) -- People is a shared directory, not an
admin-only function.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser
from app.modules.people.schemas import (
    CompanyListResponse,
    CompanyRead,
    CompanyWriteRequest,
    PersonListResponse,
    PersonRead,
    PersonWriteRequest,
)
from app.modules.people.service import (
    CompanyHasPeopleError,
    CompanyNotFoundError,
    PersonNotFoundError,
    create_company,
    create_person,
    delete_company,
    delete_person,
    get_company,
    get_person,
    list_companies,
    list_company_people,
    list_people,
    update_company,
    update_person,
)

companies_router = APIRouter(prefix="/companies", tags=["people"])
people_router = APIRouter(prefix="/people", tags=["people"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@companies_router.post("", status_code=status.HTTP_201_CREATED)
async def create_company_endpoint(
    payload: CompanyWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> CompanyRead:
    """Create a company in the caller's own organisation."""
    company = await create_company(
        session,
        organisation_id=current_user.organisation_id,
        name=payload.name,
        type=payload.type,
        address=payload.address,
        phone=payload.phone,
        general_email=payload.general_email,
        notes=payload.notes,
        created_by_id=current_user.id,
    )
    return CompanyRead.model_validate(company)


@companies_router.get("")
async def list_companies_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CompanyListResponse:
    """Paginated list of companies in the caller's own organisation."""
    companies, total = await list_companies(
        session, organisation_id=current_user.organisation_id, limit=limit, offset=offset
    )
    return CompanyListResponse(
        items=[CompanyRead.model_validate(c) for c in companies],
        total=total,
        limit=limit,
        offset=offset,
    )


@companies_router.get("/{company_id}")
async def get_company_endpoint(
    company_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> CompanyRead:
    """Fetch one company. `404` if it's not in the caller's own organisation."""
    try:
        company = await get_company(
            session, organisation_id=current_user.organisation_id, company_id=company_id
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return CompanyRead.model_validate(company)


@companies_router.patch("/{company_id}")
async def update_company_endpoint(
    company_id: uuid.UUID,
    payload: CompanyWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> CompanyRead:
    """Update a company. `404` if it's not in the caller's own organisation."""
    try:
        company = await update_company(
            session,
            organisation_id=current_user.organisation_id,
            company_id=company_id,
            updated_by_id=current_user.id,
            name=payload.name,
            type=payload.type,
            address=payload.address,
            phone=payload.phone,
            general_email=payload.general_email,
            notes=payload.notes,
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return CompanyRead.model_validate(company)


@companies_router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_endpoint(
    company_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    """Delete a company. `404` if missing; `409` if it still has people referencing it."""
    try:
        await delete_company(
            session, organisation_id=current_user.organisation_id, company_id=company_id
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    except CompanyHasPeopleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@companies_router.get("/{company_id}/people")
async def list_company_people_endpoint(
    company_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PersonListResponse:
    """Paginated list of contacts for one company. `404` if the company isn't in the
    caller's own organisation."""
    try:
        people, total = await list_company_people(
            session,
            organisation_id=current_user.organisation_id,
            company_id=company_id,
            limit=limit,
            offset=offset,
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return PersonListResponse(
        items=[PersonRead.model_validate(p) for p in people],
        total=total,
        limit=limit,
        offset=offset,
    )


@people_router.post("", status_code=status.HTTP_201_CREATED)
async def create_person_endpoint(
    payload: PersonWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> PersonRead:
    """Create a person (employee or company contact) in the caller's own organisation.

    `404` if `company_id` is set but doesn't exist in this organisation.
    """
    try:
        person = await create_person(
            session,
            organisation_id=current_user.organisation_id,
            company_id=payload.company_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            role=payload.role,
            department=payload.department,
            notes=payload.notes,
            is_employee=payload.is_employee,
            created_by_id=current_user.id,
        )
    except CompanyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company not found"
        ) from exc
    return PersonRead.model_validate(person)


@people_router.get("")
async def list_people_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    company_id: uuid.UUID | None = None,
    is_employee: bool | None = None,
    department: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PersonListResponse:
    """Paginated, filterable list of people in the caller's own organisation."""
    people, total = await list_people(
        session,
        organisation_id=current_user.organisation_id,
        company_id=company_id,
        is_employee=is_employee,
        department=department,
        search=search,
        limit=limit,
        offset=offset,
    )
    return PersonListResponse(
        items=[PersonRead.model_validate(p) for p in people],
        total=total,
        limit=limit,
        offset=offset,
    )


@people_router.get("/{person_id}")
async def get_person_endpoint(
    person_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> PersonRead:
    """Fetch one person. `404` if it's not in the caller's own organisation."""
    try:
        person = await get_person(
            session, organisation_id=current_user.organisation_id, person_id=person_id
        )
    except PersonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
    return PersonRead.model_validate(person)


@people_router.patch("/{person_id}")
async def update_person_endpoint(
    person_id: uuid.UUID,
    payload: PersonWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> PersonRead:
    """Update a person. `404` if the person, or the given `company_id`, isn't in the
    caller's own organisation."""
    try:
        person = await update_person(
            session,
            organisation_id=current_user.organisation_id,
            person_id=person_id,
            updated_by_id=current_user.id,
            company_id=payload.company_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            role=payload.role,
            department=payload.department,
            notes=payload.notes,
            is_employee=payload.is_employee,
        )
    except (PersonNotFoundError, CompanyNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PersonRead.model_validate(person)


@people_router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person_endpoint(
    person_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> None:
    """Delete a person. `404` if not in the caller's own organisation."""
    try:
        await delete_person(
            session, organisation_id=current_user.organisation_id, person_id=person_id
        )
    except PersonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Person not found"
        ) from exc
