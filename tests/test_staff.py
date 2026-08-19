from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import User
from tests.conftest import TestingSessionLocal
from tests.helpers import auth, create_staff, login, owner_token


def test_owner_creates_staff(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    body = create_staff(client, token, email="staff@acme.com", full_name="Mia Staff")

    assert body["email"] == "staff@acme.com"
    assert body["full_name"] == "Mia Staff"
    assert body["role"] == "STAFF"
    assert body["is_active"] is True
    assert body["assigned_invoice_count"] == 0


def test_create_staff_duplicate_email_conflicts(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    create_staff(client, token, email="dup@acme.com")
    response = client.post(
        "/api/v1/staff",
        headers=auth(token),
        json={"email": "dup@acme.com", "full_name": "Other", "password": "staffpass123"},
    )
    assert response.status_code == 409


def test_create_staff_requires_owner(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    response = client.post(
        "/api/v1/staff",
        headers=auth(staff_token),
        json={"email": "other@acme.com", "full_name": "X", "password": "staffpass123"},
    )
    assert response.status_code == 403


def test_list_staff_is_org_scoped(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    create_staff(client, token_a, email="s1@a.com")
    create_staff(client, token_a, email="s2@a.com")

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    create_staff(client, token_b, email="s1@b.com")

    response = client.get("/api/v1/staff", headers=auth(token_a))
    assert response.status_code == 200
    emails = {member["email"] for member in response.json()}
    assert emails == {"s1@a.com", "s2@a.com"}
    assert "s1@b.com" not in emails


def test_get_staff_cross_org_404(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    staff_a = create_staff(client, token_a, email="s1@a.com")

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")

    response = client.get(f"/api/v1/staff/{staff_a['id']}", headers=auth(token_b))
    assert response.status_code == 404


def test_get_staff_rejects_owner_as_staff(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    me = client.get("/api/v1/auth/me", headers=auth(token)).json()

    response = client.get(f"/api/v1/staff/{me['id']}", headers=auth(token))
    assert response.status_code == 404


def test_update_staff_fields_and_password(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    staff = create_staff(client, token, email="staff@acme.com")

    response = client.patch(
        f"/api/v1/staff/{staff['id']}",
        headers=auth(token),
        json={"full_name": "Renamed Staff"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed Staff"

    client.patch(
        f"/api/v1/staff/{staff['id']}",
        headers=auth(token),
        json={"password": "newpass456"},
    )
    assert (
        login(client, email="staff@acme.com", password="newpass456")["user"]["role"]
        == "STAFF"
    )
    old = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@acme.com", "password": "staffpass123"},
    )
    assert old.status_code == 401


def test_deactivate_staff_blocks_login(client: TestClient) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    staff = create_staff(client, token, email="staff@acme.com")

    response = client.delete(f"/api/v1/staff/{staff['id']}", headers=auth(token))
    assert response.status_code == 204

    assert (
        client.get(f"/api/v1/staff/{staff['id']}", headers=auth(token)).json()[
            "is_active"
        ]
        is False
    )

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@acme.com", "password": "staffpass123"},
    )
    assert blocked.status_code == 403


def test_staff_member_can_view_own_org_but_not_staff_roster(
    client: TestClient,
) -> None:
    token = owner_token(client, email="org@acme.com", organization_name="Acme Corp")
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    assert client.get("/api/v1/staff", headers=auth(staff_token)).status_code == 403
    assert client.get("/api/v1/auth/me", headers=auth(staff_token)).status_code == 200


def test_deactivated_staff_are_not_created_in_other_org(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    staff_b = create_staff(client, token_b, email="staff@b.com")

    session = TestingSessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == "staff@b.com"))
        assert user is not None
        assert user.organization_id == session.scalar(
            select(User).where(User.email == "b@acme.com")
        ).organization_id  # type: ignore[union-attr]
    finally:
        session.close()

    response = client.get(f"/api/v1/staff/{staff_b['id']}", headers=auth(token_a))
    assert response.status_code == 404
