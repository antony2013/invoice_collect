from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.models import AuditLog
from tests.conftest import TestingSessionLocal
from tests.helpers import auth, create_client, create_staff, login, owner_token


def test_owner_can_list_logs_with_actor_name(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    create_client(client, token)

    response = client.get("/api/v1/audit-logs", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 2
    actions = [entry["action"] for entry in body["items"]]
    assert "client.created" in actions
    assert "auth.register" in actions
    assert all(entry["actor_name"] == "Owner" for entry in body["items"])

    times = [entry["created_at"] for entry in body["items"]]
    assert times == sorted(times, reverse=True)


def test_audit_logs_owner_only(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    response = client.get("/api/v1/audit-logs", headers=auth(staff_token))
    assert response.status_code == 403


def test_audit_logs_cross_org_isolation(client: TestClient) -> None:
    token_a = owner_token(client, email="a@acme.com", organization_name="Org A")
    create_client(client, token_a)

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    body = client.get("/api/v1/audit-logs", headers=auth(token_b)).json()
    assert "client.created" not in [entry["action"] for entry in body["items"]]


def test_audit_logs_filter_by_action_and_resource_type(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    create_client(client, token)
    create_staff(client, token, email="staff@acme.com")

    by_action = client.get(
        "/api/v1/audit-logs",
        headers=auth(token),
        params={"action": "client.created"},
    ).json()
    assert by_action["total"] == 1

    by_type = client.get(
        "/api/v1/audit-logs",
        headers=auth(token),
        params={"resource_type": "user"},
    ).json()
    assert by_type["total"] == 2
    assert all(entry["resource_type"] == "user" for entry in by_type["items"])


def test_audit_logs_pagination(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    create_client(client, token)
    create_staff(client, token, email="s1@acme.com")
    create_staff(client, token, email="s2@acme.com")

    page1 = client.get(
        "/api/v1/audit-logs",
        headers=auth(token),
        params={"page_size": 2, "page": 1},
    ).json()
    assert page1["total"] == 4
    assert len(page1["items"]) == 2

    page2 = client.get(
        "/api/v1/audit-logs",
        headers=auth(token),
        params={"page_size": 2, "page": 2},
    ).json()
    ids1 = {entry["id"] for entry in page1["items"]}
    ids2 = {entry["id"] for entry in page2["items"]}
    assert len(ids1 | ids2) == 4


def test_audit_logs_created_at_range_filter(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    org_id = client.get("/api/v1/auth/me", headers=auth(token)).json()[
        "organization_id"
    ]

    session = TestingSessionLocal()
    try:
        session.add(
            AuditLog(
                organization_id=uuid.UUID(org_id),
                action="test.past",
                created_at=datetime.now(UTC) - timedelta(days=30),
            )
        )
        session.commit()
    finally:
        session.close()

    recent_only = client.get(
        "/api/v1/audit-logs",
        headers=auth(token),
        params={"created_after": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
    ).json()
    actions = [entry["action"] for entry in recent_only["items"]]
    assert "test.past" not in actions
    assert "auth.register" in actions


def test_audit_logs_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/audit-logs").status_code == 401
