"""Pydantic schemas for organisation-scoped user management, per docs/API.md."""

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole
from app.modules.auth.schemas import UserRead


class UserCreateRequest(BaseModel):
    """POST /api/v1/users request body."""

    email: EmailStr
    full_name: str
    password: str
    role: UserRole = UserRole.MEMBER


class UserUpdateRequest(BaseModel):
    """PATCH /api/v1/users/{id} request body — all fields optional (partial update)."""

    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserListResponse(BaseModel):
    """GET /api/v1/users response body, per docs/API.md#pagination."""

    items: list[UserRead]
    total: int
    limit: int
    offset: int
