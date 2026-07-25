"""Unit tests for app/modules/people/service.py (SQLite, ORM-level only).

Per docs/modules/People.md and the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#3-people-module):
organisation-scoped CRUD for companies/people, creator/updater attribution, the
companies-with-contacts delete guard, and cross-organisation lookups raising a
not-found error (never silently returning another organisation's row).
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.people.models  # noqa: F401
    from app.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Default Organisation", slug="default")
        session.add(org)
        await session.commit()
        return org.id


@pytest.fixture
async def other_organisation_id(session_maker: SessionMaker) -> uuid.UUID:
    async with session_maker() as session:
        org = Organisation(name="Other Organisation", slug="other")
        session.add(org)
        await session.commit()
        return org.id


@pytest.fixture
async def user_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.models.user import User

    async with session_maker() as session:
        user = User(
            organisation_id=organisation_id,
            email="creator@example.com",
            hashed_password="irrelevant",
            full_name="Creator",
        )
        session.add(user)
        await session.commit()
        return user.id


async def test_create_company_sets_creator_and_updater(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.CUSTOMER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=user_id,
        )

    assert company.created_by_id == user_id
    assert company.updated_by_id == user_id
    assert company.type == CompanyType.CUSTOMER


async def test_get_company_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import CompanyNotFoundError, create_company, get_company

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=other_organisation_id,
            name="Other Org Co",
            type=CompanyType.OTHER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CompanyNotFoundError):
            await get_company(session, organisation_id=organisation_id, company_id=company.id)


async def test_list_companies_scopes_to_organisation_and_paginates(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company, list_companies

    async with session_maker() as session:
        for i in range(3):
            await create_company(
                session,
                organisation_id=organisation_id,
                name=f"Company {i}",
                type=CompanyType.OTHER,
                address=None,
                phone=None,
                general_email=None,
                notes=None,
                created_by_id=None,
            )
        await create_company(
            session,
            organisation_id=other_organisation_id,
            name="Other Org Co",
            type=CompanyType.OTHER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        companies, total = await list_companies(
            session, organisation_id=organisation_id, limit=2, offset=0
        )

    assert total == 3
    assert len(companies) == 2
    assert all(c.organisation_id == organisation_id for c in companies)


async def test_update_company_changes_fields_and_updater(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company, update_company

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.OTHER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        updated = await update_company(
            session,
            organisation_id=organisation_id,
            company_id=company.id,
            updated_by_id=user_id,
            name="Acme Limited",
            type=CompanyType.SUPPLIER,
            address="1 Main St",
            phone=None,
            general_email=None,
            notes=None,
        )

    assert updated.name == "Acme Limited"
    assert updated.type == CompanyType.SUPPLIER
    assert updated.address == "1 Main St"
    assert updated.updated_by_id == user_id


async def test_delete_company_succeeds_when_no_people(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import (
        CompanyNotFoundError,
        create_company,
        delete_company,
        get_company,
    )

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.OTHER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        await delete_company(session, organisation_id=organisation_id, company_id=company.id)

    async with session_maker() as session:
        with pytest.raises(CompanyNotFoundError):
            await get_company(session, organisation_id=organisation_id, company_id=company.id)


async def test_delete_company_rejects_when_it_has_people(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import (
        CompanyHasPeopleError,
        create_company,
        create_person,
        delete_company,
    )

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.CUSTOMER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )
        await create_person(
            session,
            organisation_id=organisation_id,
            company_id=company.id,
            first_name="John",
            last_name="Smith",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=False,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CompanyHasPeopleError):
            await delete_company(session, organisation_id=organisation_id, company_id=company.id)


async def test_create_person_as_contact_validates_company_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import CompanyNotFoundError, create_company, create_person

    async with session_maker() as session:
        other_org_company = await create_company(
            session,
            organisation_id=other_organisation_id,
            name="Other Org Co",
            type=CompanyType.CUSTOMER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CompanyNotFoundError):
            await create_person(
                session,
                organisation_id=organisation_id,
                company_id=other_org_company.id,
                first_name="John",
                last_name="Smith",
                email=None,
                phone=None,
                role=None,
                department=None,
                notes=None,
                is_employee=False,
                created_by_id=None,
            )


async def test_list_people_filters_by_company_employee_flag_and_search(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import create_company, create_person, list_people

    async with session_maker() as session:
        company = await create_company(
            session,
            organisation_id=organisation_id,
            name="Acme Ltd",
            type=CompanyType.SUPPLIER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )
        await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Alice",
            last_name="Employee",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )
        await create_person(
            session,
            organisation_id=organisation_id,
            company_id=company.id,
            first_name="Bob",
            last_name="Contactperson",
            email="bob@acme.example.com",
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=False,
            created_by_id=None,
        )

    async with session_maker() as session:
        employees, employees_total = await list_people(
            session,
            organisation_id=organisation_id,
            company_id=None,
            is_employee=True,
            search=None,
            limit=50,
            offset=0,
        )
        contacts, contacts_total = await list_people(
            session,
            organisation_id=organisation_id,
            company_id=company.id,
            is_employee=None,
            search=None,
            limit=50,
            offset=0,
        )
        search_results, search_total = await list_people(
            session,
            organisation_id=organisation_id,
            company_id=None,
            is_employee=None,
            search="contactperson",
            limit=50,
            offset=0,
        )

    assert employees_total == 1
    assert employees[0].first_name == "Alice"
    assert contacts_total == 1
    assert contacts[0].first_name == "Bob"
    assert search_total == 1
    assert search_results[0].first_name == "Bob"


async def test_list_people_filters_by_department(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.service import create_person, list_people

    async with session_maker() as session:
        await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Alice",
            last_name="Quality",
            email=None,
            phone=None,
            role=None,
            department="Quality",
            notes=None,
            is_employee=True,
            created_by_id=None,
        )
        await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Bob",
            last_name="Engineering",
            email=None,
            phone=None,
            role=None,
            department="Engineering",
            notes=None,
            is_employee=True,
            created_by_id=None,
        )

    async with session_maker() as session:
        quality_people, quality_total = await list_people(
            session,
            organisation_id=organisation_id,
            company_id=None,
            is_employee=None,
            department="Quality",
            search=None,
            limit=50,
            offset=0,
        )

    assert quality_total == 1
    assert quality_people[0].first_name == "Alice"


async def test_update_person_changes_fields_and_updater(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.people.service import create_person, update_person

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Alice",
            last_name="Employee",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )

    async with session_maker() as session:
        updated = await update_person(
            session,
            organisation_id=organisation_id,
            person_id=person.id,
            updated_by_id=user_id,
            first_name="Alice",
            last_name="Employeeson",
            email="alice@example.com",
            phone=None,
            role="Manager",
            department="Quality",
            notes=None,
            is_employee=True,
            company_id=None,
        )

    assert updated.last_name == "Employeeson"
    assert updated.role == "Manager"
    assert updated.updated_by_id == user_id


async def test_get_person_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.people.service import PersonNotFoundError, create_person, get_person

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=other_organisation_id,
            company_id=None,
            first_name="Other",
            last_name="OrgPerson",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(PersonNotFoundError):
            await get_person(session, organisation_id=organisation_id, person_id=person.id)


async def test_delete_person_removes_the_row(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.service import (
        PersonNotFoundError,
        create_person,
        delete_person,
        get_person,
    )

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Alice",
            last_name="Employee",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )

    async with session_maker() as session:
        await delete_person(session, organisation_id=organisation_id, person_id=person.id)

    async with session_maker() as session:
        with pytest.raises(PersonNotFoundError):
            await get_person(session, organisation_id=organisation_id, person_id=person.id)


async def test_list_company_people_raises_not_found_for_cross_organisation_company(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import CompanyType
    from app.modules.people.service import (
        CompanyNotFoundError,
        create_company,
        list_company_people,
    )

    async with session_maker() as session:
        other_org_company = await create_company(
            session,
            organisation_id=other_organisation_id,
            name="Other Org Co",
            type=CompanyType.CUSTOMER,
            address=None,
            phone=None,
            general_email=None,
            notes=None,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CompanyNotFoundError):
            await list_company_people(
                session,
                organisation_id=organisation_id,
                company_id=other_org_company.id,
                limit=50,
                offset=0,
            )
