"""Pydantic schemas for the authentication API, per docs/API.md#authentication."""

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login request body."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """A user's public profile — never includes `hashed_password`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organisation_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool


class TokenResponse(BaseModel):
    """POST /api/v1/auth/login response body."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
