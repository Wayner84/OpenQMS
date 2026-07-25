"""Unit tests for the People module's ORM models (SQLite, ORM-level only).

Per docs/modules/People.md and the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md#3-people-module):
a `Person` with a null `company_id` is an employee; one with a populated `company_id`
is a contact at a customer/supplier `Company`. The `is_employee`/`company_id`
invariant itself is enforced at the schema/service layer (tested separately), not by
a DB constraint -- these tests only prove the ORM mapping and FK relationships work.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.people.models  # noqa: F401  (registers Company/Person on Base.metadata)
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


async def test_company_round_trips_with_default_type(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import Company, CompanyType

    async with session_maker() as session:
        company = Company(organisation_id=organisation_id, name="Acme Ltd")
        session.add(company)
        await session.commit()

        assert isinstance(company.id, uuid.UUID)
        assert company.type == CompanyType.OTHER


async def test_person_as_employee_has_no_company(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import Person

    async with session_maker() as session:
        employee = Person(
            organisation_id=organisation_id,
            first_name="Jane",
            last_name="Doe",
            is_employee=True,
        )
        session.add(employee)
        await session.commit()

        assert employee.company_id is None
        assert employee.is_employee is True


async def test_person_as_contact_references_a_company(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.people.models import Company, Person

    async with session_maker() as session:
        company = Company(organisation_id=organisation_id, name="Acme Ltd")
        session.add(company)
        await session.flush()

        contact = Person(
            organisation_id=organisation_id,
            company_id=company.id,
            first_name="John",
            last_name="Smith",
            is_employee=False,
        )
        session.add(contact)
        await session.commit()

        assert contact.company_id == company.id


async def test_company_supports_multiple_contacts(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from sqlalchemy import select

    from app.modules.people.models import Company, Person

    async with session_maker() as session:
        company = Company(organisation_id=organisation_id, name="Acme Ltd")
        session.add(company)
        await session.flush()

        session.add_all(
            [
                Person(
                    organisation_id=organisation_id,
                    company_id=company.id,
                    first_name="Contact",
                    last_name=f"Number{i}",
                    is_employee=False,
                )
                for i in range(3)
            ]
        )
        await session.commit()

        result = await session.execute(select(Person).where(Person.company_id == company.id))
        contacts = result.scalars().all()

    assert len(contacts) == 3
