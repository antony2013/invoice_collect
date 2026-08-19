from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import (
    auth,
    create_client,
    create_invoice,
    create_staff,
    login,
    owner_token,
)

_ITEMS = [
    {"description": "Consulting", "quantity": "2.00", "unit_price": "150.00"},
    {"description": "License", "quantity": "1.00", "unit_price": "99.99"},
]


def _setup_owner_and_client(
    client: TestClient, *, org: str = "Acme Corp", email: str = "owner@acme.com"
) -> tuple[str, dict[str, Any]]:
    token = owner_token(client, email=email, organization_name=org)
    return token, create_client(client, token)


def test_create_invoice_computes_totals(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    body = create_invoice(client, token, client_id=client_rec["id"], items=_ITEMS)

    assert body["status"] == "PENDING"
    assert body["invoice_number"].startswith("INV-")
    assert body["client_name"] == "Globex"
    assert body["total_amount"] == "399.99"
    amounts = {item["description"]: item["amount"] for item in body["items"]}
    assert amounts == {"Consulting": "300.00", "License": "99.99"}
    assert body["files"] == []


def test_create_invoice_custom_number_and_empty_items(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    body = create_invoice(
        client,
        token,
        client_id=client_rec["id"],
        invoice_number="INV-2026-0001",
    )
    assert body["invoice_number"] == "INV-2026-0001"
    assert body["total_amount"] == "0.00"
    assert body["items"] == []


def test_duplicate_invoice_number_conflicts_per_org(client: TestClient) -> None:
    token_a, client_a = _setup_owner_and_client(client, email="a@acme.com", org="Org A")
    create_invoice(
        client,
        token_a,
        client_id=client_a["id"],
        invoice_number="INV-DUP",
    )
    dup = client.post(
        "/api/v1/invoices",
        headers=auth(token_a),
        json={
            "client_id": client_a["id"],
            "invoice_date": "2026-08-02",
            "invoice_number": "INV-DUP",
        },
    )
    assert dup.status_code == 409

    token_b, client_b = _setup_owner_and_client(client, email="b@acme.com", org="Org B")
    other = client.post(
        "/api/v1/invoices",
        headers=auth(token_b),
        json={
            "client_id": client_b["id"],
            "invoice_date": "2026-08-02",
            "invoice_number": "INV-DUP",
        },
    )
    assert other.status_code == 201


def test_create_invoice_cross_org_client_404(client: TestClient) -> None:
    token_a, _ = _setup_owner_and_client(client, email="a@acme.com", org="Org A")
    token_b, client_b = _setup_owner_and_client(client, email="b@acme.com", org="Org B")

    response = client.post(
        "/api/v1/invoices",
        headers=auth(token_a),
        json={"client_id": client_b["id"], "invoice_date": "2026-08-01"},
    )
    assert response.status_code == 404


def test_staff_can_create_and_view_invoice(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    body = create_invoice(client, staff_token, client_id=client_rec["id"], items=_ITEMS)
    detail = client.get(f"/api/v1/invoices/{body['id']}", headers=auth(staff_token))
    assert detail.status_code == 200
    assert detail.json()["invoice_number"] == body["invoice_number"]


def test_list_invoices_filters_and_paginates(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    inv_pending = create_invoice(client, token, client_id=client_rec["id"], items=_ITEMS)
    create_invoice(
        client,
        token,
        client_id=client_rec["id"],
        items=_ITEMS,
        invoice_number="INV-B",
    )

    all_resp = client.get(
        "/api/v1/invoices", headers=auth(token), params={"page_size": 1}
    )
    assert all_resp.status_code == 200
    body = all_resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1

    client.patch(
        f"/api/v1/invoices/{inv_pending['id']}",
        headers=auth(token),
        json={"status": "PROCESSING"},
    )
    filtered = client.get(
        "/api/v1/invoices", headers=auth(token), params={"status": "PROCESSING"}
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == inv_pending["id"]


def test_get_invoice_cross_org_404(client: TestClient) -> None:
    token_a, client_a = _setup_owner_and_client(client, email="a@acme.com", org="Org A")
    inv = create_invoice(client, token_a, client_id=client_a["id"], items=_ITEMS)

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    assert (
        client.get(f"/api/v1/invoices/{inv['id']}", headers=auth(token_b)).status_code
        == 404
    )


def test_status_transition_rules(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    inv = create_invoice(client, token, client_id=client_rec["id"])

    bad = client.patch(
        f"/api/v1/invoices/{inv['id']}", headers=auth(token), json={"status": "COMPLETED"}
    )
    assert bad.status_code == 400
    assert "transition" in bad.json()["detail"]

    ok = client.patch(
        f"/api/v1/invoices/{inv['id']}", headers=auth(token), json={"status": "PROCESSING"}
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "PROCESSING"

    cancelled = client.patch(
        f"/api/v1/invoices/{inv['id']}", headers=auth(token), json={"status": "CANCELLED"}
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_update_replaces_items_and_recomputes_total(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    inv = create_invoice(client, token, client_id=client_rec["id"], items=_ITEMS)

    response = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"items": [{"description": "Solo", "quantity": "3", "unit_price": "10.00"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_amount"] == "30.00"
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "Solo"


def test_update_assignee_must_be_same_org_and_active(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    create_staff(client, token, email="staff@acme.com")
    inv = create_invoice(client, token, client_id=client_rec["id"])

    other = owner_token(client, email="x@acme.com", organization_name="Other Org")
    other_staff = create_staff(client, other, email="other@staff.com")

    response = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"assigned_to_id": other_staff["id"]},
    )
    assert response.status_code == 404

    me = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assigned = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"assigned_to_id": me["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["assigned_to_name"] == "Owner"


def test_update_clear_notes_and_assignment(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    inv = create_invoice(
        client,
        token,
        client_id=client_rec["id"],
        notes="initial note",
        assigned_to_id=client.get("/api/v1/auth/me", headers=auth(token)).json()["id"],
    )
    assert inv["notes"] == "initial note"

    response = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"notes": None, "assigned_to_id": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["notes"] is None
    assert body["assigned_to_id"] is None


def test_delete_invoice_owner_only(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    inv = create_invoice(client, token, client_id=client_rec["id"])
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    forbidden = client.delete(f"/api/v1/invoices/{inv['id']}", headers=auth(staff_token))
    assert forbidden.status_code == 403

    ok = client.delete(f"/api/v1/invoices/{inv['id']}", headers=auth(token))
    assert ok.status_code == 204
    assert (
        client.get(f"/api/v1/invoices/{inv['id']}", headers=auth(token)).status_code
        == 404
    )


def test_invoices_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/invoices").status_code == 401


def test_staff_create_auto_assigns_to_self(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]
    me = client.get("/api/v1/auth/me", headers=auth(staff_token)).json()

    body = create_invoice(client, staff_token, client_id=client_rec["id"], items=_ITEMS)
    assert body["assigned_to_id"] == me["id"]


def test_staff_cannot_change_assignment(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff = create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]
    inv = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff["id"]
    )

    unassign = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(staff_token),
        json={"assigned_to_id": None},
    )
    assert unassign.status_code == 403
    assert "assignment" in unassign.json()["detail"]

    me = client.get("/api/v1/auth/me", headers=auth(staff_token)).json()
    reassign = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(staff_token),
        json={"assigned_to_id": me["id"]},
    )
    assert reassign.status_code == 403


def test_owner_cannot_reassign_in_progress_invoice(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff_a = create_staff(client, token, email="a@staff.com")
    staff_b = create_staff(client, token, email="b@staff.com")
    inv = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff_a["id"]
    )
    client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"status": "PROCESSING"},
    )

    for status in ("PROCESSING", "REVIEW"):
        client.patch(
            f"/api/v1/invoices/{inv['id']}",
            headers=auth(token),
            json={"status": status},
        )
        reassign = client.patch(
            f"/api/v1/invoices/{inv['id']}",
            headers=auth(token),
            json={"assigned_to_id": staff_b["id"]},
        )
        assert reassign.status_code == 400
        assert "being worked on" in reassign.json()["detail"]
        assert client.get(
            f"/api/v1/invoices/{inv['id']}", headers=auth(token)
        ).json()["assigned_to_id"] == staff_a["id"]

        unassign = client.patch(
            f"/api/v1/invoices/{inv['id']}",
            headers=auth(token),
            json={"assigned_to_id": None},
        )
        assert unassign.status_code == 400


def test_owner_can_reassign_pending_invoice(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff_a = create_staff(client, token, email="a@staff.com")
    staff_b = create_staff(client, token, email="b@staff.com")
    inv = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff_a["id"]
    )

    reassign = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"assigned_to_id": staff_b["id"]},
    )
    assert reassign.status_code == 200
    assert reassign.json()["assigned_to_id"] == staff_b["id"]


def test_reassign_same_assignee_allowed_while_in_progress(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff = create_staff(client, token, email="staff@acme.com")
    inv = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff["id"]
    )
    client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"status": "PROCESSING"},
    )

    noop = client.patch(
        f"/api/v1/invoices/{inv['id']}",
        headers=auth(token),
        json={"assigned_to_id": staff["id"]},
    )
    assert noop.status_code == 200
    assert noop.json()["assigned_to_id"] == staff["id"]


def test_staff_can_only_update_own_assigned_invoice(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff_a = create_staff(client, token, email="a@staff.com")
    staff_b = create_staff(client, token, email="b@staff.com")
    token_a = login(client, email="a@staff.com", password="staffpass123")["access_token"]
    mine = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff_a["id"]
    )
    other = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff_b["id"]
    )

    ok = client.patch(
        f"/api/v1/invoices/{mine['id']}",
        headers=auth(token_a),
        json={"notes": "working on it"},
    )
    assert ok.status_code == 200
    assert ok.json()["notes"] == "working on it"

    forbidden = client.patch(
        f"/api/v1/invoices/{other['id']}",
        headers=auth(token_a),
        json={"notes": "not mine"},
    )
    assert forbidden.status_code == 403
    assert "assigned" in forbidden.json()["detail"]

    owner_can = client.patch(
        f"/api/v1/invoices/{other['id']}",
        headers=auth(token),
        json={"notes": "owner override"},
    )
    assert owner_can.status_code == 200


def test_staff_list_scoped_to_assigned(client: TestClient) -> None:
    token, client_rec = _setup_owner_and_client(client)
    staff = create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]
    create_invoice(client, token, client_id=client_rec["id"], items=_ITEMS)
    assigned = create_invoice(
        client,
        token,
        client_id=client_rec["id"],
        items=_ITEMS,
        assigned_to_id=staff["id"],
    )

    listing = client.get("/api/v1/invoices", headers=auth(staff_token)).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == assigned["id"]

    owner_listing = client.get("/api/v1/invoices", headers=auth(token)).json()
    assert owner_listing["total"] == 2
