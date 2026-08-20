from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from tests.helpers import (
    auth,
    create_client,
    create_invoice,
    create_staff,
    login,
    owner_token,
)


def _shift_month(day: date, delta: int) -> date:
    total = day.year * 12 + (day.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


def _seed(client: TestClient) -> tuple[str, str]:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    client_a = create_client(client, token, name="Globex")
    client_b = create_client(client, token, name="Initech")
    now = datetime.now(UTC).date()
    prev = _shift_month(now, -1)

    inv1 = create_invoice(
        client,
        token,
        client_id=client_a["id"],
        invoice_date=now.isoformat(),
        items=[{"description": "Consulting", "quantity": "2", "unit_price": "150.00"}],
    )
    inv2 = create_invoice(
        client,
        token,
        client_id=client_a["id"],
        invoice_date=prev.isoformat(),
        items=[{"description": "Retainer", "quantity": "1", "unit_price": "100.00"}],
    )
    inv3 = create_invoice(
        client,
        token,
        client_id=client_b["id"],
        invoice_date=now.isoformat(),
        items=[{"description": "License", "quantity": "1", "unit_price": "50.00"}],
    )

    client.patch(
        f"/api/v1/invoices/{inv1['id']}", headers=auth(token), json={"status": "PROCESSING"}
    )
    client.patch(
        f"/api/v1/invoices/{inv2['id']}", headers=auth(token), json={"status": "CANCELLED"}
    )
    return token, inv3["id"]


def test_report_summary_counts_and_exclusions(client: TestClient) -> None:
    token, _ = _seed(client)

    summary = client.get("/api/v1/reports/summary", headers=auth(token)).json()
    assert summary["total_invoices"] == 3
    assert summary["total_billed"] == "350.00"
    expected_status = {"PENDING": 1, "PROCESSING": 1, "COMPLETED": 0, "REVIEW": 0, "CANCELLED": 1}
    assert summary["by_status"] == expected_status

    by_month = {entry["year_month"]: entry for entry in summary["monthly"]}
    now = datetime.now(UTC).date()
    current_key = f"{now.year:04d}-{now.month:02d}"
    prev = _shift_month(now, -1)
    prev_key = f"{prev.year:04d}-{prev.month:02d}"
    assert by_month[current_key]["count"] == 2
    assert by_month[current_key]["amount"] == "350.00"
    assert by_month[prev_key]["count"] == 0
    assert by_month[prev_key]["amount"] == "0.00"

    names = [(entry["client_name"], entry["total_amount"]) for entry in summary["top_clients"]]
    assert names == [("Globex", "300.00"), ("Initech", "50.00")]


def test_report_summary_months_param(client: TestClient) -> None:
    token, _ = _seed(client)

    summary = client.get(
        "/api/v1/reports/summary", headers=auth(token), params={"months": 1}
    ).json()
    now = datetime.now(UTC).date()
    current_key = f"{now.year:04d}-{now.month:02d}"
    prev = _shift_month(now, -1)
    prev_key = f"{prev.year:04d}-{prev.month:02d}"
    keys = [entry["year_month"] for entry in summary["monthly"]]
    assert keys == [current_key]
    assert prev_key not in keys


def test_report_top_clients_limit(client: TestClient) -> None:
    token, _ = _seed(client)

    summary = client.get(
        "/api/v1/reports/summary", headers=auth(token), params={"limit": 1}
    ).json()
    assert len(summary["top_clients"]) == 1
    assert summary["top_clients"][0]["client_name"] == "Globex"


def test_report_cross_org_isolation(client: TestClient) -> None:
    _seed(client)

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    summary = client.get("/api/v1/reports/summary", headers=auth(token_b)).json()
    assert summary["total_invoices"] == 0
    assert summary["total_billed"] == "0.00"
    expected_status = {"PENDING": 0, "PROCESSING": 0, "COMPLETED": 0, "REVIEW": 0, "CANCELLED": 0}
    assert summary["by_status"] == expected_status
    assert summary["top_clients"] == []
    assert all(entry["count"] == 0 for entry in summary["monthly"])


def test_staff_cannot_access_reports(client: TestClient) -> None:
    token, _ = _seed(client)
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    response = client.get("/api/v1/reports/summary", headers=auth(staff_token))
    assert response.status_code == 403


def test_reports_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/reports/summary").status_code == 401
