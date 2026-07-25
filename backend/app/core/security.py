"""Password hashing and JWT access tokens, per docs/Architecture.md#security-baseline
and the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md).

Password hashing uses Argon2id (argon2-cffi directly, not passlib — see
docs/DecisionLog.md). JWT access tokens are HS256, carrying `sub` (user id), `org`
(organisation id), `role`, and `ver` (the user's token_version at issue time, which
implements the logout/revocation strategy: `decode_access_token` callers must compare
`ver` against the current user row and reject on mismatch).
"""

import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import BaseModel

from app.models.user import User, UserRole

__all__ = [
    "TokenError",
    "TokenPayload",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]

_ALGORITHM = "HS256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id. Never store or log the plaintext."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return True if `password` matches `hashed_password`.

    Never raises: a malformed or foreign hash is treated as a non-match rather than
    propagating an exception, so callers get a plain boolean.
    """
    try:
        return _hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False


class TokenError(Exception):
    """Raised for any invalid, expired, or malformed access token."""


class TokenPayload(BaseModel):
    """Typed claims decoded from a validated access token."""

    sub: uuid.UUID
    org: uuid.UUID
    role: UserRole
    ver: int


def create_access_token(user: User, *, secret_key: str, expire_minutes: int) -> str:
    """Issue a signed access token for `user`, expiring in `expire_minutes`."""
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "org": str(user.organisation_id),
        "role": user.role.value,
        "ver": user.token_version,
        "iat": now,
        "exp": now + expire_minutes * 60,
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str, *, secret_key: str) -> TokenPayload:
    """Validate `token`'s signature and expiry, and return its typed claims.

    Raises `TokenError` for any expired, tampered, or malformed token.
    """
    try:
        raw_payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token is invalid or expired") from exc

    try:
        return TokenPayload.model_validate(raw_payload)
    except Exception as exc:
        raise TokenError("Token payload is malformed") from exc
