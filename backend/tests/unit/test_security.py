"""Unit tests for password hashing and JWT access tokens (app/core/security.py).

Per the Milestone 1 plan
(.hermes/plans/2026-07-25-milestone-1-auth-organisations-people.md): Argon2id
hashing via argon2-cffi, HS256 JWTs carrying sub/org/role/ver/exp/iat claims, with
`ver` implementing the logout/revocation strategy.
"""

import time
import uuid

import jwt
import pytest

from app.models.user import User, UserRole


def _make_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "organisation_id": uuid.uuid4(),
        "email": "user@example.com",
        "hashed_password": "irrelevant-for-token-tests",
        "full_name": "Test User",
        "role": UserRole.MEMBER,
        "token_version": 0,
    }
    defaults.update(overrides)
    return User(**defaults)


def test_hash_password_produces_a_verifiable_but_different_string() -> None:
    from app.core.security import hash_password, verify_password

    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    from app.core.security import hash_password, verify_password

    hashed = hash_password("correct horse battery staple")

    assert verify_password("wrong password", hashed) is False


def test_verify_password_rejects_malformed_hash_instead_of_raising() -> None:
    from app.core.security import verify_password

    assert verify_password("anything", "not-a-real-argon2-hash") is False


def test_create_and_decode_access_token_round_trips_claims() -> None:
    from app.core.security import create_access_token, decode_access_token

    user = _make_user(role=UserRole.ADMIN, token_version=3)
    token = create_access_token(user, secret_key="test-secret", expire_minutes=60)

    payload = decode_access_token(token, secret_key="test-secret")

    assert payload.sub == user.id
    assert payload.org == user.organisation_id
    assert payload.role == UserRole.ADMIN
    assert payload.ver == 3


def test_decode_access_token_rejects_expired_token() -> None:
    from app.core.security import TokenError, create_access_token, decode_access_token

    user = _make_user()
    token = create_access_token(user, secret_key="test-secret", expire_minutes=-1)

    with pytest.raises(TokenError):
        decode_access_token(token, secret_key="test-secret")


def test_decode_access_token_rejects_tampered_signature() -> None:
    from app.core.security import TokenError, create_access_token, decode_access_token

    user = _make_user()
    token = create_access_token(user, secret_key="test-secret", expire_minutes=60)

    with pytest.raises(TokenError):
        decode_access_token(token, secret_key="a-different-secret")


def test_decode_access_token_rejects_garbage_input() -> None:
    from app.core.security import TokenError, decode_access_token

    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt", secret_key="test-secret")


def test_create_access_token_sets_expiry_in_the_future(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.security import create_access_token

    user = _make_user()
    before = int(time.time())
    token = create_access_token(user, secret_key="test-secret", expire_minutes=60)
    decoded = jwt.decode(token, "test-secret", algorithms=["HS256"])

    assert decoded["exp"] > before
    assert decoded["exp"] - decoded["iat"] == 60 * 60
