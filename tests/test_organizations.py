from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import auth, create_staff, login, owner_token


def test_get_my_organization(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    response = client.get("/api/v1/organizations/me", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Corp"
    assert body["is_active"] is True
    assert body["staff_count"] == 0
    assert body["client_count"] == 0
    assert body["invoice_count"] == 0


def test_update_organization_name(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    response = client.patch(
        "/api/v1/organizations/me",
        headers=auth(token),
        json={"name": "Acme Corp Ltd"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Corp Ltd"


def test_organization_update_requires_owner(client: TestClient) -> None:
    owner = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    create_staff(client, owner, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    response = client.patch(
        "/api/v1/organizations/me",
        headers=auth(staff_token),
        json={"name": "Hacked Name"},
    )
    assert response.status_code == 403


def test_get_organization_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/organizations/me")
    assert response.status_code == 401
