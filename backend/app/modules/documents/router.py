"""Document Management endpoints: categories, tags, and documents (metadata only --
version upload/download/preview land in a later Milestone 2 slice's
app/modules/documents/storage.py).

Per docs/API.md and the Milestone 2 plan's "Permissions summary": listing/viewing and
document create/edit are open to any active user; category/tag mutation is
admin-only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentAdmin, CurrentUser
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.schemas import (
    CategoryListResponse,
    CategoryRead,
    CategoryWriteRequest,
    DocumentListResponse,
    DocumentRead,
    DocumentVersionListResponse,
    DocumentVersionRead,
    DocumentWriteRequest,
    TagCreateRequest,
    TagListResponse,
    TagRead,
)
from app.modules.documents.service import (
    CategoryHasChildrenError,
    CategoryInUseError,
    CategoryNotFoundError,
    DocumentNotFoundError,
    OwnerNotFoundError,
    TagAlreadyExistsError,
    TagNotFoundError,
    create_category,
    create_document,
    create_tag,
    delete_category,
    delete_document,
    delete_tag,
    get_category,
    get_document,
    list_categories,
    list_document_tags,
    list_document_versions,
    list_documents,
    list_tags,
    update_category,
    update_document,
)

categories_router = APIRouter(prefix="/document-categories", tags=["documents"])
tags_router = APIRouter(prefix="/document-tags", tags=["documents"])
documents_router = APIRouter(prefix="/documents", tags=["documents"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def _document_read(session: AsyncSession, document: Document) -> DocumentRead:
    tags = await list_document_tags(session, document_id=document.id)
    return DocumentRead(
        id=document.id,
        organisation_id=document.organisation_id,
        category_id=document.category_id,
        number=document.number,
        title=document.title,
        owner_id=document.owner_id,
        status=document.status,
        current_version_id=document.current_version_id,
        created_by_id=document.created_by_id,
        updated_by_id=document.updated_by_id,
        tags=[TagRead.model_validate(tag) for tag in tags],
    )


# --- Categories --------------------------------------------------------------


@categories_router.post("", status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(
    payload: CategoryWriteRequest, current_user: CurrentAdmin, session: SessionDependency
) -> CategoryRead:
    try:
        category = await create_category(
            session,
            organisation_id=current_user.organisation_id,
            name=payload.name,
            parent_category_id=payload.parent_category_id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found"
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.get("")
async def list_categories_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CategoryListResponse:
    categories, total = await list_categories(
        session, organisation_id=current_user.organisation_id, limit=limit, offset=offset
    )
    return CategoryListResponse(
        items=[CategoryRead.model_validate(c) for c in categories],
        total=total,
        limit=limit,
        offset=offset,
    )


@categories_router.get("/{category_id}")
async def get_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> CategoryRead:
    try:
        category = await get_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.patch("/{category_id}")
async def update_category_endpoint(
    category_id: uuid.UUID,
    payload: CategoryWriteRequest,
    current_user: CurrentAdmin,
    session: SessionDependency,
) -> CategoryRead:
    try:
        category = await update_category(
            session,
            organisation_id=current_user.organisation_id,
            category_id=category_id,
            name=payload.name,
            parent_category_id=payload.parent_category_id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    return CategoryRead.model_validate(category)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_category(
            session, organisation_id=current_user.organisation_id, category_id=category_id
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except (CategoryHasChildrenError, CategoryInUseError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# --- Tags ------------------------------------------------------------------


@tags_router.post("", status_code=status.HTTP_201_CREATED)
async def create_tag_endpoint(
    payload: TagCreateRequest, current_user: CurrentAdmin, session: SessionDependency
) -> TagRead:
    try:
        tag = await create_tag(
            session, organisation_id=current_user.organisation_id, name=payload.name
        )
    except TagAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TagRead.model_validate(tag)


@tags_router.get("")
async def list_tags_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TagListResponse:
    tags, total = await list_tags(
        session,
        organisation_id=current_user.organisation_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TagListResponse(
        items=[TagRead.model_validate(t) for t in tags], total=total, limit=limit, offset=offset
    )


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag_endpoint(
    tag_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_tag(session, organisation_id=current_user.organisation_id, tag_id=tag_id)
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc


# --- Documents ---------------------------------------------------------------


@documents_router.post("", status_code=status.HTTP_201_CREATED)
async def create_document_endpoint(
    payload: DocumentWriteRequest, current_user: CurrentUser, session: SessionDependency
) -> DocumentRead:
    try:
        document = await create_document(
            session,
            organisation_id=current_user.organisation_id,
            title=payload.title,
            category_id=payload.category_id,
            owner_id=payload.owner_id,
            tag_ids=payload.tag_ids,
            created_by_id=current_user.id,
        )
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found"
        ) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc
    return await _document_read(session, document)


@documents_router.get("")
async def list_documents_endpoint(
    current_user: CurrentUser,
    session: SessionDependency,
    category_id: uuid.UUID | None = None,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    owner_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    documents, total = await list_documents(
        session,
        organisation_id=current_user.organisation_id,
        category_id=category_id,
        status=status_filter,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )
    items = [await _document_read(session, document) for document in documents]
    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


@documents_router.get("/{document_id}")
async def get_document_endpoint(
    document_id: uuid.UUID, current_user: CurrentUser, session: SessionDependency
) -> DocumentRead:
    try:
        document = await get_document(
            session, organisation_id=current_user.organisation_id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return await _document_read(session, document)


@documents_router.patch("/{document_id}")
async def update_document_endpoint(
    document_id: uuid.UUID,
    payload: DocumentWriteRequest,
    current_user: CurrentUser,
    session: SessionDependency,
) -> DocumentRead:
    try:
        document = await update_document(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            updated_by_id=current_user.id,
            title=payload.title,
            category_id=payload.category_id,
            owner_id=payload.owner_id,
            tag_ids=payload.tag_ids,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        ) from exc
    except OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found"
        ) from exc
    except TagNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found") from exc
    return await _document_read(session, document)


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: uuid.UUID, current_user: CurrentAdmin, session: SessionDependency
) -> None:
    try:
        await delete_document(
            session, organisation_id=current_user.organisation_id, document_id=document_id
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc


@documents_router.get("/{document_id}/versions")
async def list_document_versions_endpoint(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentVersionListResponse:
    try:
        versions, total = await list_document_versions(
            session,
            organisation_id=current_user.organisation_id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    return DocumentVersionListResponse(
        items=[DocumentVersionRead.model_validate(v) for v in versions],
        total=total,
        limit=limit,
        offset=offset,
    )
