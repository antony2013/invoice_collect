from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import get_settings

ALGORITHM = "HS256"

_pwd_hasher = PasswordHasher()


class InvalidToken(RuntimeError):
    """Raised when a JWT cannot be decoded or is malformed."""


def hash_password(password: str) -> str:
    return _pwd_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _pwd_hasher.verify(password_hash, password)
    except VerificationError:
        return False


def _secret_key() -> str:
    return get_settings().secret_key


def create_access_token(
    *, user_id: UUID, role: str, organization_id: UUID, jti: UUID
) -> tuple[str, datetime]:
    """Create a signed access token. Returns (token, expires_at)."""
    settings = get_settings()
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "org_id": str(organization_id),
        "jti": str(jti),
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and verify a JWT. Raises InvalidToken on any failure."""
    try:
        return jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except ExpiredSignatureError as exc:
        raise InvalidToken("Token has expired") from exc
    except InvalidTokenError as exc:
        raise InvalidToken("Invalid token") from exc
