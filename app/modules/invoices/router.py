from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.audit import write_audit_log
from app.core.crud import get_owned_or_404
from app.core.deps import CurrentUser, DbDep, Owner
from app.core.params import PageParam, PageSizeParam
from app.models import Client, Invoice, InvoiceFile, InvoiceItem, User, UserRole
from app.models.base import utcnow
from app.models.enums import InvoiceStatus
from app.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceDetailResponse,
    InvoiceFileResponse,
    InvoiceItemPayload,
    InvoiceItemResponse,
    InvoiceListEnvelope,
    InvoiceListResponse,
    InvoiceUpdate,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

StatusFilter = Annotated[InvoiceStatus | None, Query(alias="status")]
ClientIdFilter = Annotated[UUID | None, Query()]

_TWO_PLACES = Decimal("0.01")

ALLOWED_STATUS_TRANSITIONS: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.PENDING: {InvoiceStatus.PROCESSING, InvoiceStatus.CANCELLED},
    InvoiceStatus.PROCESSING: {
        InvoiceStatus.COMPLETED,
        InvoiceStatus.REVIEW,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.COMPLETED: {InvoiceStatus.REVIEW, InvoiceStatus.CANCELLED},
    InvoiceStatus.REVIEW: {
        InvoiceStatus.PROCESSING,
        InvoiceStatus.COMPLETED,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.CANCELLED: set(),
}

IN_PROGRESS_STATUSES = frozenset({InvoiceStatus.PROCESSING, InvoiceStatus.REVIEW})


def _round_amount(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _item_amount(item: InvoiceItemPayload) -> Decimal:
    return _round_amount(item.quantity * item.unit_price)


def _invoice_number() -> str:
    return f"INV-{utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _build_items(
    db: DbDep,
    invoice: Invoice,
    payloads: list[InvoiceItemPayload],
) -> None:
    invoice.items.clear()
    for payload in payloads:
        db.add(
            InvoiceItem(
                organization_id=invoice.organization_id,
                invoice_id=invoice.id,
                description=payload.description,
                quantity=payload.quantity,
                unit_price=payload.unit_price,
                amount=_item_amount(payload),
            )
        )
    invoice.total_amount = sum(
        (_item_amount(item) for item in payloads), Decimal("0")
    )


def _validate_client(db: DbDep, client_id: UUID, organization_id: UUID) -> Client:
    return get_owned_or_404(
        db,
        Client,
        record_id=client_id,
        organization_id=organization_id,
        detail="Client not found",
    )


def _validate_assignee(
    db: DbDep,
    assignee_id: UUID | None,
    organization_id: UUID,
) -> User | None:
    if assignee_id is None:
        return None
    assignee = get_owned_or_404(
        db,
        User,
        record_id=assignee_id,
        organization_id=organization_id,
        detail="Assigned user not found",
    )
    if not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign to an inactive user",
        )
    return assignee


def _get_invoice_or_404(db: DbDep, invoice_id: UUID, organization_id: UUID) -> Invoice:
    return get_owned_or_404(
        db,
        Invoice,
        record_id=invoice_id,
        organization_id=organization_id,
        detail="Invoice not found",
    )


def _require_staff_access(current_user: User, invoice: Invoice) -> None:
    """Only the staff member assigned to an invoice may work on it."""
    if current_user.role is UserRole.OWNER:
        return
    if invoice.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff can only work on invoices assigned to them",
        )


def _require_worker_role(current_user: User) -> None:
    """Client accounts must use the /clients/me endpoints instead."""
    if current_user.role is UserRole.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clients cannot access this resource",
        )


def _to_list_response(db: DbDep, invoice: Invoice) -> InvoiceListResponse:
    return InvoiceListResponse(
        id=invoice.id,
        client_id=invoice.client_id,
        client_name=invoice.client.name,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        status=invoice.status,
        currency=invoice.currency,
        total_amount=invoice.total_amount,
        assigned_to_id=invoice.assigned_to_id,
        assigned_to_name=invoice.assigned_to.full_name if invoice.assigned_to else None,
        created_at=invoice.created_at,
    )


def _file_response(file: InvoiceFile) -> InvoiceFileResponse:
    return InvoiceFileResponse(
        id=file.id,
        original_name=file.original_name,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        uploaded_by_name=file.uploader.full_name if file.uploader else None,
        created_at=file.created_at,
    )


def _to_detail_response(db: DbDep, invoice: Invoice) -> InvoiceDetailResponse:
    return InvoiceDetailResponse(
        **_to_list_response(db, invoice).model_dump(),
        notes=invoice.notes,
        updated_at=invoice.updated_at,
        items=[
            InvoiceItemResponse.model_validate(item) for item in invoice.items
        ],
        files=[_file_response(file) for file in invoice.files],
    )


@router.post(
    "", response_model=InvoiceDetailResponse, status_code=status.HTTP_201_CREATED
)
def create_invoice(
    payload: InvoiceCreate,
    current_user: CurrentUser,
    db: DbDep,
) -> InvoiceDetailResponse:
    """Create an invoice for an owned client, computing totals server-side."""
    org_id = current_user.organization_id
    _require_worker_role(current_user)
    _validate_client(db, payload.client_id, org_id)
    assigned_to_id = (
        current_user.id
        if current_user.role is UserRole.STAFF
        else payload.assigned_to_id
    )
    _validate_assignee(db, assigned_to_id, org_id)

    if payload.invoice_number is not None and db.scalar(
        select(Invoice).where(
            Invoice.organization_id == org_id,
            Invoice.invoice_number == payload.invoice_number,
        )
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An invoice with this number already exists in your organization",
        )

    invoice = Invoice(
        organization_id=org_id,
        client_id=payload.client_id,
        assigned_to_id=assigned_to_id,
        invoice_number=payload.invoice_number or _invoice_number(),
        invoice_date=payload.invoice_date,
        currency=payload.currency,
        notes=payload.notes,
        status=InvoiceStatus.PENDING,
        total_amount=Decimal("0"),
    )
    db.add(invoice)
    db.flush()
    _build_items(db, invoice, payload.items)

    write_audit_log(
        db,
        organization_id=org_id,
        actor_id=current_user.id,
        action="invoice.created",
        resource_type="invoice",
        resource_id=invoice.id,
    )
    db.commit()
    db.expire(invoice)

    return _to_detail_response(db, invoice)


@router.get("", response_model=InvoiceListEnvelope)
def list_invoices(
    current_user: CurrentUser,
    db: DbDep,
    status_filter: StatusFilter = None,
    client_id: ClientIdFilter = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> InvoiceListEnvelope:
    """List organization invoices with optional filters and pagination."""
    org_id = current_user.organization_id
    _require_worker_role(current_user)
    filters = [Invoice.organization_id == org_id]
    if current_user.role is not UserRole.OWNER:
        filters.append(Invoice.assigned_to_id == current_user.id)
    if status_filter is not None:
        filters.append(Invoice.status == status_filter)
    if client_id is not None:
        filters.append(Invoice.client_id == client_id)

    total = (
        db.scalar(select(func.count()).select_from(Invoice).where(*filters)) or 0
    )
    invoices = db.scalars(
        select(Invoice)
        .where(*filters)
        .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return InvoiceListEnvelope(
        items=[_to_list_response(db, inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(
    invoice_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> InvoiceDetailResponse:
    """Return a single invoice with items and files."""
    _require_worker_role(current_user)
    invoice = _get_invoice_or_404(db, invoice_id, current_user.organization_id)
    return _to_detail_response(db, invoice)


@router.patch("/{invoice_id}", response_model=InvoiceDetailResponse)
def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdate,
    current_user: CurrentUser,
    db: DbDep,
) -> InvoiceDetailResponse:
    """Update an invoice (fields, items, status with transition checks)."""
    org_id = current_user.organization_id
    invoice = _get_invoice_or_404(db, invoice_id, org_id)
    updates = payload.model_dump(exclude_unset=True)

    if current_user.role is not UserRole.OWNER:
        _require_staff_access(current_user, invoice)
        if "assigned_to_id" in updates:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owners can change invoice assignment",
            )

    if "status" in updates:
        requested = updates["status"]
        if requested != invoice.status and requested not in ALLOWED_STATUS_TRANSITIONS[
            invoice.status
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot transition invoice from {invoice.status.value} "
                    f"to {requested.value}"
                ),
            )
        invoice.status = requested

    if "assigned_to_id" in updates:
        requested_assignee = updates["assigned_to_id"]
        if requested_assignee != invoice.assigned_to_id:
            if invoice.status in IN_PROGRESS_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reassign an invoice while it is being worked on",
                )
        _validate_assignee(db, requested_assignee, org_id)
        invoice.assigned_to_id = requested_assignee

    if "items" in updates and updates["items"] is not None:
        _build_items(
            db,
            invoice,
            [InvoiceItemPayload(**item) for item in updates["items"]],
        )

    for field in ("invoice_date", "currency", "notes"):
        if field in updates:
            setattr(invoice, field, updates[field])

    write_audit_log(
        db,
        organization_id=org_id,
        actor_id=current_user.id,
        action="invoice.updated",
        resource_type="invoice",
        resource_id=invoice.id,
    )
    db.commit()
    db.expire(invoice)
    return _to_detail_response(db, invoice)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(
    invoice_id: UUID,
    owner: Owner,
    db: DbDep,
) -> None:
    """Delete an invoice and its items (owner only). Files are removed from storage."""
    invoice = _get_invoice_or_404(db, invoice_id, owner.organization_id)
    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="invoice.deleted",
        resource_type="invoice",
        resource_id=invoice.id,
    )
    db.delete(invoice)
    db.commit()
