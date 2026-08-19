from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient


def register_owner(
    client: TestClient,
    *,
    email: str,
    organization_name: str,
    full_name: str = "Owner",
    password: str = "strongpass123",
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


def owner_token(
    client: TestClient,
    *,
    email: str,
    organization_name: str,
) -> str:
    token = register_owner(client, email=email, organization_name=organization_name)[
        "access_token"
    ]
    return cast(str, token)


def create_staff(
    client: TestClient,
    token: str,
    *,
    email: str,
    full_name: str = "Staff User",
    password: str = "staffpass123",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/staff",
        headers=auth(token),
        json={
            "email": email,
            "full_name": full_name,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def login(
    client: TestClient,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_client(
    client: TestClient,
    token: str,
    *,
    name: str = "Globex",
    email: str | None = "contact@globex.com",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/clients",
        headers=auth(token),
        json={"name": name, "email": email},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def create_invoice(
    client: TestClient,
    token: str,
    *,
    client_id: str,
    items: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "client_id": client_id,
        "invoice_date": "2026-08-01",
    }
    if items is not None:
        payload["items"] = items
    payload.update(overrides)
    response = client.post(
        "/api/v1/invoices",
        headers=auth(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())
