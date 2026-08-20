from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import FakeMinioService
from tests.helpers import (
    auth,
    create_client,
    create_invoice,
    create_staff,
    login,
    owner_token,
)

_PDF = b"%PDF-1.4 fake invoice bytes"


def _upload(
    client: TestClient,
    token: str,
    invoice_id: str,
    *,
    content: bytes = _PDF,
    filename: str = "invoice.pdf",
) -> Any:
    return client.post(
        f"/api/v1/invoices/{invoice_id}/files",
        headers=auth(token),
        files={"upload": (filename, content, "application/pdf")},
    )


def _setup(client: TestClient) -> tuple[str, str]:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    client_rec = create_client(client, token)
    invoice = create_invoice(client, token, client_id=client_rec["id"])
    return token, invoice["id"]


def test_upload_and_download_roundtrip(client: TestClient) -> None:
    token, invoice_id = _setup(client)

    upload = _upload(client, token, invoice_id)
    assert upload.status_code == 201
    body = upload.json()
    assert body["original_name"] == "invoice.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_PDF)
    assert body["uploaded_by_name"] == "Owner"

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth(token)).json()
    assert len(detail["files"]) == 1
    assert detail["files"][0]["id"] == body["id"]

    download = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{body['id']}/download",
        headers=auth(token),
    )
    assert download.status_code == 200
    assert download.content == _PDF
    assert download.headers["content-type"].startswith("application/pdf")
    assert "invoice.pdf" in download.headers["content-disposition"]


def test_object_key_layout(client: TestClient, fake_minio: FakeMinioService) -> None:
    token, invoice_id = _setup(client)
    _upload(client, token, invoice_id)
    keys = list(fake_minio.objects.keys())
    assert len(keys) == 1
    assert keys[0].startswith("organizations/")
    assert "/invoices/" in keys[0]
    assert keys[0].endswith("-invoice.pdf")


def test_upload_cross_org_invoice_404(client: TestClient) -> None:
    token_a, invoice_id = _setup(client)
    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    assert _upload(client, token_b, invoice_id).status_code == 404


def test_empty_upload_rejected(client: TestClient) -> None:
    token, invoice_id = _setup(client)
    assert _upload(client, token, invoice_id, content=b"").status_code == 400


def test_download_cross_org_404(client: TestClient) -> None:
    token_a, invoice_id = _setup(client)
    file_id = _upload(client, token_a, invoice_id).json()["id"]

    token_b = owner_token(client, email="b@acme.com", organization_name="Org B")
    response = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}/download",
        headers=auth(token_b),
    )
    assert response.status_code == 404


def test_download_missing_object_404(
    client: TestClient, fake_minio: FakeMinioService
) -> None:
    token, invoice_id = _setup(client)
    file_id = _upload(client, token, invoice_id).json()["id"]

    fake_minio.objects.clear()
    response = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}/download",
        headers=auth(token),
    )
    assert response.status_code == 404


def test_delete_file_removes_object_and_row(
    client: TestClient, fake_minio: FakeMinioService
) -> None:
    token, invoice_id = _setup(client)
    file_id = _upload(client, token, invoice_id).json()["id"]

    response = client.delete(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}", headers=auth(token)
    )
    assert response.status_code == 204
    assert fake_minio.objects == {}

    detail = client.get(f"/api/v1/invoices/{invoice_id}", headers=auth(token)).json()
    assert detail["files"] == []

    download = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}/download",
        headers=auth(token),
    )
    assert download.status_code == 404


def test_staff_can_upload_and_download_assigned_invoice(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    client_rec = create_client(client, token)
    staff = create_staff(client, token, email="staff@acme.com")
    invoice_id = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff["id"]
    )["id"]
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    uploaded = _upload(client, staff_token, invoice_id)
    assert uploaded.status_code == 201
    assert uploaded.json()["uploaded_by_name"] == "Staff User"

    file_id = uploaded.json()["id"]
    download = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}/download",
        headers=auth(staff_token),
    )
    assert download.status_code == 200
    assert download.content == _PDF


def test_staff_cannot_touch_unassigned_invoice_files(client: TestClient) -> None:
    token, invoice_id = _setup(client)
    create_staff(client, token, email="staff@acme.com")
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    uploaded = _upload(client, staff_token, invoice_id)
    assert uploaded.status_code == 403

    file_id = _upload(client, token, invoice_id).json()["id"]
    download = client.get(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}/download",
        headers=auth(staff_token),
    )
    assert download.status_code == 403


def test_staff_cannot_delete_file(client: TestClient) -> None:
    token = owner_token(client, email="owner@acme.com", organization_name="Acme Corp")
    client_rec = create_client(client, token)
    staff = create_staff(client, token, email="staff@acme.com")
    invoice_id = create_invoice(
        client, token, client_id=client_rec["id"], assigned_to_id=staff["id"]
    )["id"]
    file_id = _upload(client, token, invoice_id).json()["id"]
    staff_token = login(client, email="staff@acme.com", password="staffpass123")[
        "access_token"
    ]

    response = client.delete(
        f"/api/v1/invoices/{invoice_id}/files/{file_id}", headers=auth(staff_token)
    )
    assert response.status_code == 403


def test_files_require_auth(client: TestClient) -> None:
    token, invoice_id = _setup(client)
    assert (
        client.post(f"/api/v1/invoices/{invoice_id}/files").status_code == 401
    )
