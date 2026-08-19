from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User
from tests.conftest import TestingSessionLocal


def register(
    client: TestClient,
    *,
    email: str = "owner@acme.com",
    password: str = "strongpass123",
    organization_name: str = "Acme Corp",
    full_name: str = "Jane Owner",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": organization_name,
            "full_name": full_name,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_creates_organization_and_owner(client: TestClient) -> None:
    body = register(client)

    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 0
    assert body["expires_in"] > 0
    assert body["user"]["role"] == "OWNER"
    assert body["user"]["email"] == "owner@acme.com"
    assert body["user"]["organization_name"] == "Acme Corp"
    assert uuid.UUID(body["user"]["id"])
    assert uuid.UUID(body["user"]["organization_id"])


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Org",
            "full_name": "Other User",
            "email": "owner@acme.com",
            "password": "anotherpass123",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Corp",
            "full_name": "Jane Owner",
            "email": "weak@acme.com",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_login_success_and_wrong_password(client: TestClient) -> None:
    register(client)

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@acme.com", "password": "strongpass123"},
    )
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == "owner@acme.com"

    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@acme.com", "password": "wrongpass123"},
    )
    assert bad.status_code == 401
    assert "Invalid email or password" in bad.json()["detail"]


def test_me_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

    bad_token = client.get("/api/v1/auth/me", headers=auth_header("not-a-jwt"))
    assert bad_token.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    token = register(client)["access_token"]
    response = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@acme.com"
    assert body["role"] == "OWNER"
    assert body["full_name"] == "Jane Owner"


def test_logout_revokes_token(client: TestClient) -> None:
    token = register(client)["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth_header(token)).status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=auth_header(token))
    assert logout.status_code == 204

    after = client.get("/api/v1/auth/me", headers=auth_header(token))
    assert after.status_code == 401
    assert "revoked" in after.json()["detail"]


def test_inactive_user_cannot_log_in(client: TestClient) -> None:
    register(client)
    session = TestingSessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == "owner@acme.com"))
        assert user is not None
        user.is_active = False
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@acme.com", "password": "strongpass123"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]
