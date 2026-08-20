from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import Uuid
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    AuditLog,
    Client,
    Invoice,
    InvoiceFile,
    InvoiceItem,
    InvoiceStatus,
    Organization,
    User,
    UserRole,
)
from tests.conftest import TestingSessionLocal


def make_org(name: str = "Acme Corp") -> Organization:
    return Organization(name=name)


def make_user(
    org: Organization,
    email: str,
    role: UserRole = UserRole.STAFF,
) -> User:
    return User(
        organization=org,
        email=email,
        full_name="Test User",
        password_hash="not-a-real-hash",
        role=role,
    )


def make_client(org: Organization, name: str = "Client A") -> Client:
    return Client(organization=org, name=name)


def make_invoice(
    org: Organization,
    client: Client,
    number: str = "INV-2026-001",
    staff: User | None = None,
) -> Invoice:
    return Invoice(
        organization=org,
        client=client,
        assigned_to=staff,
        invoice_number=number,
        invoice_date=date(2026, 1, 15),
        total_amount=Decimal("250.00"),
    )


def test_organization_with_users(db: Session) -> None:
    org = make_org()
    owner = make_user(org, "owner@acme.com", UserRole.OWNER)
    staff = make_user(org, "staff@acme.com", UserRole.STAFF)
    db.add(org)
    db.commit()

    assert org.id is not None
    assert isinstance(org.id, uuid.UUID)
    assert owner.id is not None and staff.id is not None
    assert owner.organization is org
    assert {user.email for user in org.users} == {"owner@acme.com", "staff@acme.com"}
    assert owner.role is UserRole.OWNER
    assert staff.role is UserRole.STAFF


def test_invoice_relationships_and_default_status(db: Session) -> None:
    org = make_org()
    staff = make_user(org, "staff@acme.com")
    client = make_client(org, "Client A")
    invoice = make_invoice(org, client, staff=staff)

    invoice.items.append(
        InvoiceItem(
            invoice=invoice,
            organization=org,
            description="Consulting",
            quantity=Decimal("2.00"),
            unit_price=Decimal("125.00"),
            amount=Decimal("250.00"),
        )
    )
    invoice.files.append(
        InvoiceFile(
            invoice=invoice,
            organization=org,
            original_name="invoice.pdf",
            object_key=f"organizations/{org.id}/clients/{client.id}/invoices/2026/01/invoice.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            uploader=staff,
        )
    )
    audit = AuditLog(
        organization=org,
        actor=staff,
        action="invoice.created",
        resource_type="invoice",
        details={"number": "INV-2026-001"},
    )
    db.add_all([org, audit])
    db.commit()

    assert invoice.status is InvoiceStatus.PENDING
    assert invoice.client is client
    assert invoice.assigned_to is staff
    assert invoice.organization_id == org.id
    assert invoice.items[0].amount == Decimal("250.00")
    assert invoice.files[0].original_name == "invoice.pdf"
    assert invoice.files[0].uploader is staff
    assert audit.actor is not None
    assert audit.actor.email == "staff@acme.com"
    assert len(staff.assigned_invoices) == 1
    assert len(client.invoices) == 1


def test_invoice_number_unique_per_organization(db: Session) -> None:
    org_a = make_org("Org A")
    org_b = make_org("Org B")
    client_a = make_client(org_a, "Client A")
    client_b = make_client(org_b, "Client B")
    db.add_all(
        [
            org_a,
            org_b,
            make_invoice(org_a, client_a, "INV-1"),
            make_invoice(org_b, client_b, "INV-1"),
        ]
    )
    db.commit()

    duplicate = make_invoice(org_a, client_a, "INV-1")
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_email_is_globally_unique(db: Session) -> None:
    org = make_org()
    db.add_all([org, make_user(org, "duplicate@acme.com"), make_user(org, "duplicate@acme.com")])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cascade_delete_invoice_removes_items_and_files(db: Session) -> None:
    org = make_org()
    client = make_client(org)
    invoice = make_invoice(org, client)
    invoice.items.append(
        InvoiceItem(
            organization=org,
            description="Item",
            quantity=Decimal("1.00"),
            unit_price=Decimal("10.00"),
            amount=Decimal("10.00"),
        )
    )
    invoice.files.append(
        InvoiceFile(
            organization=org,
            original_name="inv.pdf",
            object_key="some/key/inv.pdf",
        )
    )
    db.add(org)
    db.commit()

    invoice_id = invoice.id
    item_id = invoice.items[0].id
    file_id = invoice.files[0].id

    db.delete(invoice)
    db.commit()

    session = TestingSessionLocal()
    try:
        assert session.get(Invoice, invoice_id) is None
        assert session.get(InvoiceItem, item_id) is None
        assert session.get(InvoiceFile, file_id) is None
    finally:
        session.close()


def test_organization_owned_tables_have_organization_id() -> None:
    org_owned = {
        "users",
        "clients",
        "invoices",
        "invoice_items",
        "invoice_files",
        "audit_logs",
    }
    for table_name in org_owned:
        table = Base.metadata.tables[table_name]
        assert "organization_id" in table.columns, table_name
        assert not table.c.organization_id.nullable, table_name


def test_all_tables_use_single_uuid_primary_key() -> None:
    for table_name, table in Base.metadata.tables.items():
        pk_columns = list(table.primary_key.columns)
        assert len(pk_columns) == 1, table_name
        assert isinstance(pk_columns[0].type, Uuid), table_name
