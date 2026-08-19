from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import auth, create_client, login, owner_token

PDF_BYTES = b"%PDF-1.4 fake invoice content"


def _invite_client(
    client: TestClient,
    token: str,
    client_id: str,
    *,
    email: str = "client@acme.com",
    password: str = "clientpass123",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/clients/{client_id}/invite",
        headers=auth(token),
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _invited_client_login(
    client: TestClient,
    *,
    email: str = "client@acme.com",
    password: str = "clientpass123",
) -> str:
    body = login(client, email=email, password=password)
    return str(body["access_token"])


def _upload_invoice(
    client: TestClient,
    token: str,
    *,
    filename: str = "invoice.pdf",
    content: bytes = PDF_BYTES,
    notes: str | None = None,
) -> dict[str, Any]:
    data: dict[str, str] = {}
    if notes is not None:
        data["notes"] = notes
    response = client.post(
        "/api/v1/clients/me/invoices/upload",
        headers=auth(token),
        files={"upload": (filename, content, "application/pdf")},
        data=data,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


# --- Owner invite API ---------------------------------------------------


def test_owner_invites_client_account(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)

    body = _invite_client(client, token, created["id"])
    assert body["account_email"] == "client@acme.com"
    assert body["name"] == "Globex"

    assert (
        client.get(
            f"/api/v1/clients/{created['id']}",
            headers=auth(token),
        ).json()["account_email"]
        == "client@acme.com"
    )


def test_invite_existing_account_conflict(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])

    response = client.post(
        f"/api/v1/clients/{created['id']}/invite",
        headers=auth(token),
        json={"email": "other@acme.com", "password": "clientpass123"},
    )
    assert response.status_code == 409


def test_invite_duplicate_email_conflict(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    first = create_client(client, token, email="dup@acme.com")
    second = create_client(client, token, name="Initech", email="other@acme.com")
    _invite_client(client, token, first["id"], email="dup@acme.com")

    response = client.post(
        f"/api/v1/clients/{second['id']}/invite",
        headers=auth(token),
        json={"email": "dup@acme.com", "password": "clientpass123"},
    )
    assert response.status_code == 409


def test_invite_inactive_client_rejected(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    client.patch(
        f"/api/v1/clients/{created['id']}",
        headers=auth(token),
        json={"is_active": False},
    )

    response = client.post(
        f"/api/v1/clients/{created['id']}/invite",
        headers=auth(token),
        json={"email": "client@acme.com", "password": "clientpass123"},
    )
    assert response.status_code == 400


def test_invite_requires_owner(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Corp",
            "full_name": "Other Owner",
            "email": "other@corp.com",
            "password": "strongpass123",
        },
    )
    other_token = register.json()["access_token"]

    response = client.post(
        f"/api/v1/clients/{created['id']}/invite",
        headers=auth(other_token),
        json={"email": "client@acme.com", "password": "clientpass123"},
    )
    assert response.status_code == 404


def test_reset_client_password(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    old_token = _invited_client_login(client)

    response = client.patch(
        f"/api/v1/clients/{created['id']}/invite",
        headers=auth(token),
        json={"password": "newpassword456"},
    )
    assert response.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@acme.com", "password": "clientpass123"},
    )
    assert old_login.status_code == 401
    assert old_token

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "client@acme.com", "password": "newpassword456"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["access_token"] != old_token


# --- Client-side API ----------------------------------------------------


def test_client_profile(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)

    response = client.get("/api/v1/clients/me", headers=auth(client_tok))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Globex"
    assert body["email"] == "contact@globex.com"


def test_client_upload_creates_pending_invoice(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)

    body = _upload_invoice(client, client_tok, notes="please process")
    assert body["status"] == "PENDING"
    assert body["total_amount"] == "0.00"
    assert body["notes"] == "please process"
    assert body["assigned_to_id"] is None
    assert len(body["files"]) == 1
    assert body["files"][0]["original_name"] == "invoice.pdf"
    assert body["files"][0]["uploaded_by_name"] == "Globex"


def test_client_lists_and_gets_own_invoices(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)
    uploaded = _upload_invoice(client, client_tok)

    listing = client.get("/api/v1/clients/me/invoices", headers=auth(client_tok))
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == uploaded["id"]

    detail = client.get(
        f"/api/v1/clients/me/invoices/{uploaded['id']}",
        headers=auth(client_tok),
    )
    assert detail.status_code == 200
    assert detail.json()["files"][0]["original_name"] == "invoice.pdf"


def test_client_downloads_own_file(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)
    uploaded = _upload_invoice(client, client_tok)
    file_id = uploaded["files"][0]["id"]

    response = client.get(
        f"/api/v1/clients/me/invoices/{uploaded['id']}/files/{file_id}/download",
        headers=auth(client_tok),
    )
    assert response.status_code == 200
    assert response.content == PDF_BYTES


def test_client_adds_file_to_invoice(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)
    uploaded = _upload_invoice(client, client_tok)

    response = client.post(
        f"/api/v1/clients/me/invoices/{uploaded['id']}/files",
        headers=auth(client_tok),
        files={"upload": ("second.pdf", b"%PDF-1.4 more", "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["original_name"] == "second.pdf"


def test_client_cannot_see_other_clients_invoices(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    client_a = create_client(client, token)
    client_b = create_client(client, token, name="Initech", email="b@acme.com")
    _invite_client(client, token, client_a["id"], email="a@acme.com")
    _invite_client(client, token, client_b["id"], email="b@acme.com")

    token_a = _invited_client_login(client, email="a@acme.com")
    token_b = _invited_client_login(client, email="b@acme.com")
    uploaded = _upload_invoice(client, token_a)

    listing_b = client.get("/api/v1/clients/me/invoices", headers=auth(token_b))
    assert listing_b.status_code == 200
    assert listing_b.json()["total"] == 0

    assert (
        client.get(
            f"/api/v1/clients/me/invoices/{uploaded['id']}",
            headers=auth(token_b),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/clients/me/invoices/{uploaded['id']}/files/"
            f"{uploaded['files'][0]['id']}/download",
            headers=auth(token_b),
        ).status_code
        == 404
    )


def test_client_blocked_from_worker_invoice_endpoints(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    client_tok = _invited_client_login(client)
    uploaded = _upload_invoice(client, client_tok)

    create_response = client.post(
        "/api/v1/invoices",
        headers=auth(client_tok),
        json={"client_id": created["id"], "invoice_date": "2026-08-01"},
    )
    assert create_response.status_code == 403

    assert (
        client.get("/api/v1/invoices", headers=auth(client_tok)).status_code == 403
    )
    assert (
        client.get(
            f"/api/v1/invoices/{uploaded['id']}", headers=auth(client_tok)
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/invoices/{uploaded['id']}",
            headers=auth(client_tok),
            json={"status": "PROCESSING"},
        ).status_code
        == 403
    )


def test_inactive_client_user_cannot_login(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    _invited_client_login(client)

    client.patch(
        f"/api/v1/clients/{created['id']}",
        headers=auth(token),
        json={"is_active": False},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "client@acme.com", "password": "clientpass123"},
    )
    assert response.status_code == 403


def test_deleting_client_removes_login_account(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    created = create_client(client, token)
    _invite_client(client, token, created["id"])
    _invited_client_login(client)

    response = client.delete(
        f"/api/v1/clients/{created['id']}", headers=auth(token)
    )
    assert response.status_code == 204

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "client@acme.com", "password": "clientpass123"},
        ).status_code
        == 401
    )
