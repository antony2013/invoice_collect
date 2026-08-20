from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import auth, create_staff, login, owner_token


def _client_payload(**overrides: str | None) -> dict[str, str | None]:
    payload: dict[str, str | None] = {
        "name": "Globex",
        "email": "contact@globex.com",
        "phone": "+1-555-0100",
        "address": "123 Main St",
        "notes": "VIP client",
    }
    payload.update(overrides)
    return payload


def test_owner_creates_client(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    response = client.post(
        "/api/v1/clients",
        headers=auth(token),
        json=_client_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Globex"
    assert body["email"] == "contact@globex.com"
    assert body["is_active"] is True
    assert body["invoice_count"] == 0
    assert body["total_billed"] == "0"
    assert body["invoices"] == []


def test_list_clients_is_org_scoped(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")

    client.post("/api/v1/clients", headers=auth(token_a), json=_client_payload(name="Acme A"))
    client.post("/api/v1/clients", headers=auth(token_b), json=_client_payload(name="Acme B"))

    response = client.get("/api/v1/clients", headers=auth(token_a))
    assert response.status_code == 200
    names = [entry["name"] for entry in response.json()]
    assert names == ["Acme A"]
    assert "Acme B" not in names


def test_get_client_cross_org_404(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    created = client.post(
        "/api/v1/clients", headers=auth(token_a), json=_client_payload()
    ).json()

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    response = client.get(f"/api/v1/clients/{created['id']}", headers=auth(token_b))
    assert response.status_code == 404


def test_update_client_fields(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = client.post(
        "/api/v1/clients", headers=auth(token), json=_client_payload()
    ).json()

    response = client.patch(
        f"/api/v1/clients/{created['id']}",
        headers=auth(token),
        json={"name": "Globex Inc", "notes": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Globex Inc"
    assert body["email"] == "contact@globex.com"
    assert body["notes"] is None


def test_delete_client(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = client.post(
        "/api/v1/clients", headers=auth(token), json=_client_payload()
    ).json()

    response = client.delete(f"/api/v1/clients/{created['id']}", headers=auth(token))
    assert response.status_code == 204

    assert (
        client.get(f"/api/v1/clients/{created['id']}", headers=auth(token)).status_code
        == 404
    )


def test_clients_require_owner(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    assert (
        client.post(
            "/api/v1/clients", headers=auth(staff_token), json=_client_payload()
        ).status_code
        == 403
    )
    assert (
        client.get("/api/v1/clients", headers=auth(staff_token)).status_code == 403
    )


def test_clients_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/clients").status_code == 401
    assert client.post("/api/v1/clients", json=_client_payload()).status_code == 401


def test_client_detail_includes_invoice_summaries(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = client.post(
        "/api/v1/clients", headers=auth(token), json=_client_payload()
    ).json()

    response = client.get(f"/api/v1/clients/{created['id']}", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["invoice_count"] == 0
    assert "invoices" in body
