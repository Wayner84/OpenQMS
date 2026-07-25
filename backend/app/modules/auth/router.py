"""Authentication endpoints: login, logout, current-user profile, per docs/API.md#authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.deps import CurrentUser
from app.core.security import create_access_token
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserRead
from app.modules.auth.service import InvalidCredentialsError, authenticate_user, revoke_tokens

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.post("/login")
async def login(
    payload: LoginRequest, session: SessionDependency, settings: SettingsDependency
) -> TokenResponse:
    """Authenticate by email/password and issue a signed access token."""
    try:
        user = await authenticate_user(session, email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        ) from exc

    access_token = create_access_token(
        user,
        secret_key=settings.jwt_secret_key,
        expire_minutes=settings.jwt_access_token_expire_minutes,
    )
    return TokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser, session: SessionDependency) -> None:
    """Invalidate every access token issued to the calling user so far."""
    await revoke_tokens(session, current_user)


@router.get("/me")
async def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's own profile."""
    return UserRead.model_validate(current_user)
