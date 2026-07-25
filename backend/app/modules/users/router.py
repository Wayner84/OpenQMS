"""Organisation-scoped user management endpoints (admin-only), per docs/API.md."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentAdmin
from app.modules.auth.schemas import UserRead
from app.modules.users.schemas import UserCreateRequest, UserListResponse, UserUpdateRequest
from app.modules.users.service import (
    DuplicateEmailError,
    LastAdminGuardError,
    UserNotFoundError,
    create_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreateRequest, current_admin: CurrentAdmin, session: SessionDependency
) -> UserRead:
    """Create a user in the admin's own organisation. `409` on duplicate email."""
    try:
        user = await create_user(
            session,
            organisation_id=current_admin.organisation_id,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=payload.role,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(user)


@router.get("")
async def list_users_endpoint(
    current_admin: CurrentAdmin,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserListResponse:
    """Paginated list of users in the admin's own organisation."""
    users, total = await list_users(
        session, organisation_id=current_admin.organisation_id, limit=limit, offset=offset
    )
    return UserListResponse(
        items=[UserRead.model_validate(user) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{user_id}")
async def update_user_endpoint(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    current_admin: CurrentAdmin,
    session: SessionDependency,
) -> UserRead:
    """Partially update a user in the admin's own organisation.

    `404` if `user_id` doesn't exist in the admin's organisation. `409` if the update
    would let an admin deactivate/demote themselves, or leave zero active admins.
    """
    try:
        user = await update_user(
            session,
            organisation_id=current_admin.organisation_id,
            acting_user=current_admin,
            target_user_id=user_id,
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except LastAdminGuardError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(user)
