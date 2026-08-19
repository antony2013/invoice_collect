from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import InvalidToken, decode_access_token
from app.database import get_db
from app.models import RevokedToken, User, UserRole

_bearer = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_v1_prefix}/auth/login",
    auto_error=True,
)

DbDep = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[str, Depends(_bearer)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(_bearer)],
    db: DbDep,
) -> User:
    """Resolve the authenticated user from the bearer token."""
    try:
        payload = decode_access_token(token)
    except InvalidToken as exc:
        raise _unauthorized(str(exc)) from exc

    if payload.get("type") != "access":
        raise _unauthorized("Invalid token type")

    sub = payload.get("sub")
    jti = payload.get("jti")
    if not isinstance(sub, str) or not isinstance(jti, str):
        raise _unauthorized("Invalid token claims")
    try:
        user_id = UUID(sub)
    except ValueError as exc:
        raise _unauthorized("Invalid token subject") from exc

    if db.scalar(select(RevokedToken).where(RevokedToken.jti == jti)) is not None:
        raise _unauthorized("Token has been revoked")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    return user


def require_owner(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency that only allows organization OWNERs through."""
    if current_user.role is not UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can perform this action",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
Owner = Annotated[User, Depends(require_owner)]
