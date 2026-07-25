"""Business logic for the People module: companies and their people (employees and
contacts). Per docs/modules/People.md and the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#3-people-module):
every operation is scoped to the caller's organisation; a company cannot be deleted
while any person still references it; creator/updater attribution is recorded on
every write.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.people.models import Company, CompanyType, Person


class CompanyNotFoundError(Exception):
    """Raised when a company id doesn't exist in the caller's organisation."""


class PersonNotFoundError(Exception):
    """Raised when a person id doesn't exist in the caller's organisation."""


class CompanyHasPeopleError(Exception):
    """Raised when deleting a company that still has people referencing it."""


async def create_company(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    name: str,
    type: CompanyType,
    address: str | None,
    phone: str | None,
    general_email: str | None,
    notes: str | None,
    created_by_id: uuid.UUID | None,
) -> Company:
    """Create a company in `organisation_id`, attributing creator and updater."""
    company = Company(
        organisation_id=organisation_id,
        name=name,
        type=type,
        address=address,
        phone=phone,
        general_email=general_email,
        notes=notes,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def get_company(
    session: AsyncSession, *, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> Company:
    """Return the company, or raise `CompanyNotFoundError` if it's not in this organisation."""
    company = (
        await session.execute(
            select(Company).where(
                Company.id == company_id, Company.organisation_id == organisation_id
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise CompanyNotFoundError(f"No company {company_id} in this organisation")
    return company


async def list_companies(
    session: AsyncSession, *, organisation_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Company], int]:
    """Return a page of companies in `organisation_id`, plus the total matching count."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(Company)
            .where(Company.organisation_id == organisation_id)
        )
    ).scalar_one()

    result = await session.execute(
        select(Company)
        .where(Company.organisation_id == organisation_id)
        .order_by(Company.created_at)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def update_company(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    updated_by_id: uuid.UUID | None,
    name: str,
    type: CompanyType,
    address: str | None,
    phone: str | None,
    general_email: str | None,
    notes: str | None,
) -> Company:
    """Replace a company's editable fields. Raises `CompanyNotFoundError` if missing."""
    company = await get_company(session, organisation_id=organisation_id, company_id=company_id)
    company.name = name
    company.type = type
    company.address = address
    company.phone = phone
    company.general_email = general_email
    company.notes = notes
    company.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(company)
    return company


async def delete_company(
    session: AsyncSession, *, organisation_id: uuid.UUID, company_id: uuid.UUID
) -> None:
    """Delete a company. Raises `CompanyHasPeopleError` if any person still references it."""
    company = await get_company(session, organisation_id=organisation_id, company_id=company_id)
    people_count = (
        await session.execute(
            select(func.count()).select_from(Person).where(Person.company_id == company_id)
        )
    ).scalar_one()
    if people_count > 0:
        raise CompanyHasPeopleError("Cannot delete a company that still has people referencing it")
    await session.delete(company)
    await session.commit()


async def list_company_people(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[Person], int]:
    """Return a page of contacts for one company. Raises `CompanyNotFoundError` if the
    company doesn't exist in this organisation."""
    await get_company(session, organisation_id=organisation_id, company_id=company_id)
    return await list_people(
        session,
        organisation_id=organisation_id,
        company_id=company_id,
        is_employee=None,
        search=None,
        limit=limit,
        offset=offset,
    )


async def create_person(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID | None,
    first_name: str,
    last_name: str,
    email: str | None,
    phone: str | None,
    role: str | None,
    department: str | None,
    notes: str | None,
    is_employee: bool,
    created_by_id: uuid.UUID | None,
) -> Person:
    """Create a person in `organisation_id`.

    If `company_id` is set, raises `CompanyNotFoundError` unless that company exists
    in the same organisation (never silently attaches a person to another
    organisation's company).
    """
    if company_id is not None:
        await get_company(session, organisation_id=organisation_id, company_id=company_id)

    person = Person(
        organisation_id=organisation_id,
        company_id=company_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        role=role,
        department=department,
        notes=notes,
        is_employee=is_employee,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
    )
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


async def get_person(
    session: AsyncSession, *, organisation_id: uuid.UUID, person_id: uuid.UUID
) -> Person:
    """Return the person, or raise `PersonNotFoundError` if not in this organisation."""
    person = (
        await session.execute(
            select(Person).where(Person.id == person_id, Person.organisation_id == organisation_id)
        )
    ).scalar_one_or_none()
    if person is None:
        raise PersonNotFoundError(f"No person {person_id} in this organisation")
    return person


async def list_people(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    company_id: uuid.UUID | None,
    is_employee: bool | None,
    department: str | None = None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Person], int]:
    """Return a page of people in `organisation_id`, optionally filtered/searched."""
    filters = [Person.organisation_id == organisation_id]
    if company_id is not None:
        filters.append(Person.company_id == company_id)
    if is_employee is not None:
        filters.append(Person.is_employee == is_employee)
    if department is not None:
        filters.append(Person.department == department)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Person.first_name.ilike(pattern),
                Person.last_name.ilike(pattern),
                Person.email.ilike(pattern),
                Person.role.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(Person).where(*filters))
    ).scalar_one()

    result = await session.execute(
        select(Person).where(*filters).order_by(Person.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def update_person(
    session: AsyncSession,
    *,
    organisation_id: uuid.UUID,
    person_id: uuid.UUID,
    updated_by_id: uuid.UUID | None,
    company_id: uuid.UUID | None,
    first_name: str,
    last_name: str,
    email: str | None,
    phone: str | None,
    role: str | None,
    department: str | None,
    notes: str | None,
    is_employee: bool,
) -> Person:
    """Replace a person's editable fields. Raises `PersonNotFoundError` if missing,
    or `CompanyNotFoundError` if `company_id` is set but not in this organisation."""
    person = await get_person(session, organisation_id=organisation_id, person_id=person_id)
    if company_id is not None:
        await get_company(session, organisation_id=organisation_id, company_id=company_id)

    person.company_id = company_id
    person.first_name = first_name
    person.last_name = last_name
    person.email = email
    person.phone = phone
    person.role = role
    person.department = department
    person.notes = notes
    person.is_employee = is_employee
    person.updated_by_id = updated_by_id
    await session.commit()
    await session.refresh(person)
    return person


async def delete_person(
    session: AsyncSession, *, organisation_id: uuid.UUID, person_id: uuid.UUID
) -> None:
    """Delete a person. Raises `PersonNotFoundError` if not in this organisation."""
    person = await get_person(session, organisation_id=organisation_id, person_id=person_id)
    await session.delete(person)
    await session.commit()
