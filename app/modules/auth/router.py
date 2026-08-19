from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from app.core.audit import write_audit_log
from app.core.deps import BearerToken, CurrentUser, DbDep
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models import Organization, RevokedToken, User, UserRole
from app.models.base import utcnow
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        organization_id=user.organization_id,
        organization_name=user.organization.name,
        created_at=user.created_at,
    )


def _build_token_response(user: User) -> TokenResponse:
    jti = uuid.uuid4()
    token, expires_at = create_access_token(
        user_id=user.id,
        role=user.role.value,
        organization_id=user.organization_id,
        jti=jti,
    )
    expires_in = int((expires_at - datetime.now(UTC)).total_seconds())
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=_to_user_response(user),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: DbDep) -> TokenResponse:
    """Register a new organization and its OWNER account."""
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    organization = Organization(name=payload.organization_name)
    user = User(
        organization=organization,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=UserRole.OWNER,
    )
    db.add(organization)
    db.commit()
    db.refresh(user)

    write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_id=user.id,
        action="auth.register",
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()

    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbDep) -> TokenResponse:
    """Authenticate with email/password and receive an access token."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow()))
    user.last_login_at = utcnow()
    write_audit_log(
        db,
        organization_id=user.organization_id,
        actor_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()

    return _build_token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_: CurrentUser, token: BearerToken, db: DbDep) -> None:
    """Revoke the current access token."""
    payload = decode_access_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    if isinstance(jti, str) and isinstance(exp, int):
        db.add(
            RevokedToken(
                jti=jti,
                expires_at=datetime.fromtimestamp(exp, tz=UTC),
            )
        )
        db.commit()


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user."""
    return _to_user_response(current_user)
