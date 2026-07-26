"""Unit tests for app/modules/documents/service.py (SQLite, ORM-level only).

Per the Milestone 2 plan: organisation-scoped CRUD for categories/tags/documents,
server-generated numbering, owner validation via the People module's own service
(never its models directly), the category delete guards, and cascading tag delete.
"""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.organisation import Organisation

SessionMaker = async_sessionmaker[AsyncSession]


@pytest.fixture
async def session_maker() -> AsyncIterator[SessionMaker]:
    import app.modules.documents.models  # noqa: F401
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


@pytest.fixture
async def person_id(session_maker: SessionMaker, organisation_id: uuid.UUID) -> uuid.UUID:
    from app.modules.people.service import create_person

    async with session_maker() as session:
        person = await create_person(
            session,
            organisation_id=organisation_id,
            company_id=None,
            first_name="Alice",
            last_name="Owner",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )
        return person.id


# --- Categories --------------------------------------------------------------


async def test_create_category_and_child(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_category

    async with session_maker() as session:
        parent = await create_category(
            session, organisation_id=organisation_id, name="Quality", parent_category_id=None
        )
    async with session_maker() as session:
        child = await create_category(
            session,
            organisation_id=organisation_id,
            name="SOPs",
            parent_category_id=parent.id,
        )

    assert child.parent_category_id == parent.id


async def test_create_category_rejects_cross_org_parent(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import CategoryNotFoundError, create_category

    async with session_maker() as session:
        other_org_parent = await create_category(
            session,
            organisation_id=other_organisation_id,
            name="Other Org Cat",
            parent_category_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CategoryNotFoundError):
            await create_category(
                session,
                organisation_id=organisation_id,
                name="Child",
                parent_category_id=other_org_parent.id,
            )


async def test_delete_category_rejects_when_it_has_children(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        CategoryHasChildrenError,
        create_category,
        delete_category,
    )

    async with session_maker() as session:
        parent = await create_category(
            session, organisation_id=organisation_id, name="Quality", parent_category_id=None
        )
        await create_category(
            session, organisation_id=organisation_id, name="SOPs", parent_category_id=parent.id
        )

    async with session_maker() as session:
        with pytest.raises(CategoryHasChildrenError):
            await delete_category(session, organisation_id=organisation_id, category_id=parent.id)


async def test_delete_category_rejects_when_in_use_by_a_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        CategoryInUseError,
        create_category,
        create_document,
        delete_category,
    )

    async with session_maker() as session:
        category = await create_category(
            session, organisation_id=organisation_id, name="Quality", parent_category_id=None
        )
        await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=category.id,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(CategoryInUseError):
            await delete_category(session, organisation_id=organisation_id, category_id=category.id)


async def test_delete_category_succeeds_when_unused(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        CategoryNotFoundError,
        create_category,
        delete_category,
        get_category,
    )

    async with session_maker() as session:
        category = await create_category(
            session, organisation_id=organisation_id, name="Quality", parent_category_id=None
        )

    async with session_maker() as session:
        await delete_category(session, organisation_id=organisation_id, category_id=category.id)

    async with session_maker() as session:
        with pytest.raises(CategoryNotFoundError):
            await get_category(session, organisation_id=organisation_id, category_id=category.id)


# --- Tags --------------------------------------------------------------------


async def test_create_tag_rejects_duplicate_name_in_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import TagAlreadyExistsError, create_tag

    async with session_maker() as session:
        await create_tag(session, organisation_id=organisation_id, name="controlled")

    async with session_maker() as session:
        with pytest.raises(TagAlreadyExistsError):
            await create_tag(session, organisation_id=organisation_id, name="controlled")


async def test_delete_tag_cascades_link_removal(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        create_document,
        create_tag,
        delete_tag,
        list_document_tags,
    )

    async with session_maker() as session:
        tag = await create_tag(session, organisation_id=organisation_id, name="controlled")
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="SOP-1",
            category_id=None,
            owner_id=None,
            tag_ids=[tag.id],
            created_by_id=None,
        )

    async with session_maker() as session:
        tags_before = await list_document_tags(session, document_id=document.id)
    assert len(tags_before) == 1

    async with session_maker() as session:
        await delete_tag(session, organisation_id=organisation_id, tag_id=tag.id)

    async with session_maker() as session:
        tags_after = await list_document_tags(session, document_id=document.id)
    assert tags_after == []


# --- Documents ---------------------------------------------------------------


async def test_create_document_generates_number_and_sets_attribution(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.documents.models import DocumentStatus
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=user_id,
        )

    assert document.number == "DOC-0001"
    assert document.status == DocumentStatus.DRAFT
    assert document.created_by_id == user_id
    assert document.updated_by_id == user_id
    assert document.current_version_id is None


async def test_create_document_numbers_sequentially(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        first = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc 1",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
    async with session_maker() as session:
        second = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc 2",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    assert first.number == "DOC-0001"
    assert second.number == "DOC-0002"


async def test_create_document_validates_owner_in_same_organisation(
    session_maker: SessionMaker, organisation_id: uuid.UUID, person_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Quality Manual",
            category_id=None,
            owner_id=person_id,
            tag_ids=[],
            created_by_id=None,
        )

    assert document.owner_id == person_id


async def test_create_document_rejects_cross_org_owner(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import OwnerNotFoundError, create_document
    from app.modules.people.service import create_person

    async with session_maker() as session:
        other_org_person = await create_person(
            session,
            organisation_id=other_organisation_id,
            company_id=None,
            first_name="Other",
            last_name="Org",
            email=None,
            phone=None,
            role=None,
            department=None,
            notes=None,
            is_employee=True,
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(OwnerNotFoundError):
            await create_document(
                session,
                organisation_id=organisation_id,
                title="Quality Manual",
                category_id=None,
                owner_id=other_org_person.id,
                tag_ids=[],
                created_by_id=None,
            )


async def test_get_document_raises_not_found_for_cross_organisation_id(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        create_document,
        get_document,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=other_organisation_id,
            title="Other Org Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await get_document(session, organisation_id=organisation_id, document_id=document.id)


async def test_list_documents_excludes_soft_deleted(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document, delete_document, list_documents

    async with session_maker() as session:
        keep = await create_document(
            session,
            organisation_id=organisation_id,
            title="Keep",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )
        gone = await create_document(
            session,
            organisation_id=organisation_id,
            title="Gone",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        await delete_document(session, organisation_id=organisation_id, document_id=gone.id)

    async with session_maker() as session:
        documents, total = await list_documents(
            session,
            organisation_id=organisation_id,
            category_id=None,
            status=None,
            owner_id=None,
            limit=50,
            offset=0,
        )

    assert total == 1
    assert documents[0].id == keep.id


async def test_delete_document_raises_not_found_when_already_deleted(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        create_document,
        delete_document,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        await delete_document(session, organisation_id=organisation_id, document_id=document.id)

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await delete_document(session, organisation_id=organisation_id, document_id=document.id)


async def test_update_document_replaces_tags(
    session_maker: SessionMaker, organisation_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        create_document,
        create_tag,
        list_document_tags,
        update_document,
    )

    async with session_maker() as session:
        tag_a = await create_tag(session, organisation_id=organisation_id, name="a")
        tag_b = await create_tag(session, organisation_id=organisation_id, name="b")
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[tag_a.id],
            created_by_id=None,
        )

    async with session_maker() as session:
        await update_document(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            updated_by_id=user_id,
            title="Doc renamed",
            category_id=None,
            owner_id=None,
            tag_ids=[tag_b.id],
        )

    async with session_maker() as session:
        tags = await list_document_tags(session, document_id=document.id)

    assert [t.id for t in tags] == [tag_b.id]


async def test_list_document_versions_raises_not_found_for_cross_org_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID, other_organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import (
        DocumentNotFoundError,
        create_document,
        list_document_versions,
    )

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=other_organisation_id,
            title="Other Org Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        with pytest.raises(DocumentNotFoundError):
            await list_document_versions(
                session,
                organisation_id=organisation_id,
                document_id=document.id,
                limit=50,
                offset=0,
            )


async def test_list_document_versions_is_empty_for_a_freshly_created_document(
    session_maker: SessionMaker, organisation_id: uuid.UUID
) -> None:
    from app.modules.documents.service import create_document, list_document_versions

    async with session_maker() as session:
        document = await create_document(
            session,
            organisation_id=organisation_id,
            title="Doc",
            category_id=None,
            owner_id=None,
            tag_ids=[],
            created_by_id=None,
        )

    async with session_maker() as session:
        versions, total = await list_document_versions(
            session,
            organisation_id=organisation_id,
            document_id=document.id,
            limit=50,
            offset=0,
        )

    assert total == 0
    assert versions == []
