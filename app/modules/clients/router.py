from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.audit import write_audit_log
from app.core.crud import get_owned_or_404
from app.core.deps import DbDep, Owner
from app.core.security import hash_password
from app.models import Client, Invoice, User, UserRole
from app.modules.clients.schemas import (
    ClientCreate,
    ClientDetailResponse,
    ClientInviteRequest,
    ClientInviteReset,
    ClientListResponse,
    ClientUpdate,
    InvoiceSummary,
)

router = APIRouter(prefix="/clients", tags=["clients"])


def _invoice_summary(invoice: Invoice) -> InvoiceSummary:
    return InvoiceSummary(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        status=invoice.status,
        total_amount=invoice.total_amount,
        assigned_to_id=invoice.assigned_to_id,
        assigned_to_name=invoice.assigned_to.full_name if invoice.assigned_to else None,
    )


def _client_list_response(client: Client) -> ClientListResponse:
    return ClientListResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        address=client.address,
        is_active=client.is_active,
        created_at=client.created_at,
        invoice_count=len(client.invoices),
        total_billed=_total_billed(client),
        account_email=client.user.email if client.user else None,
    )


def _client_detail_response(client: Client) -> ClientDetailResponse:
    invoices = sorted(
        client.invoices,
        key=lambda inv: (inv.invoice_date, inv.created_at),
        reverse=True,
    )
    return ClientDetailResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        address=client.address,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        notes=client.notes,
        invoice_count=len(invoices),
        total_billed=_total_billed(client),
        account_email=client.user.email if client.user else None,
        invoices=[_invoice_summary(inv) for inv in invoices],
    )


def _total_billed(client: Client) -> Decimal:
    return sum((inv.total_amount for inv in client.invoices), Decimal("0"))


def _get_client_or_404(
    db: DbDep,
    client_id: UUID,
    organization_id: UUID,
) -> Client:
    return get_owned_or_404(
        db,
        Client,
        record_id=client_id,
        organization_id=organization_id,
        detail="Client not found",
    )


@router.post("", response_model=ClientDetailResponse, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, owner: Owner, db: DbDep) -> ClientDetailResponse:
    """Create a client in the owner's organization."""
    client = Client(organization_id=owner.organization_id, **payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="client.created",
        resource_type="client",
        resource_id=client.id,
    )
    db.commit()

    return _client_detail_response(client)


@router.get("", response_model=list[ClientListResponse])
def list_clients(owner: Owner, db: DbDep) -> list[ClientListResponse]:
    """List all clients in the owner's organization."""
    clients = db.scalars(
        select(Client)
        .where(Client.organization_id == owner.organization_id)
        .order_by(Client.name)
    ).all()
    return [_client_list_response(client) for client in clients]


@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client(client_id: UUID, owner: Owner, db: DbDep) -> ClientDetailResponse:
    """Return a client with its invoice history."""
    client = _get_client_or_404(db, client_id, owner.organization_id)
    return _client_detail_response(client)


@router.patch("/{client_id}", response_model=ClientDetailResponse)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    owner: Owner,
    db: DbDep,
) -> ClientDetailResponse:
    """Update client details."""
    client = _get_client_or_404(db, client_id, owner.organization_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    if client.user is not None:
        client.user.is_active = client.is_active

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="client.updated",
        resource_type="client",
        resource_id=client.id,
    )
    db.commit()
    db.refresh(client)
    return _client_detail_response(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: UUID, owner: Owner, db: DbDep) -> None:
    """Delete a client, its invoices, and its linked login account."""
    client = _get_client_or_404(db, client_id, owner.organization_id)
    if client.user is not None:
        db.delete(client.user)
    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="client.deleted",
        resource_type="client",
        resource_id=client.id,
    )
    db.delete(client)
    db.commit()


@router.post(
    "/{client_id}/invite",
    response_model=ClientDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_client(
    client_id: UUID,
    payload: ClientInviteRequest,
    owner: Owner,
    db: DbDep,
) -> ClientDetailResponse:
    """Create a CLIENT login account for a client record."""
    client = _get_client_or_404(db, client_id, owner.organization_id)
    if db.scalar(
        select(User).where(
            User.organization_id == owner.organization_id,
            User.client_id == client.id,
        )
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This client already has an account",
        )
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite an inactive client",
        )
    if db.scalar(select(User).where(User.email == payload.email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        organization_id=owner.organization_id,
        email=payload.email,
        full_name=client.name,
        password_hash=hash_password(payload.password),
        role=UserRole.CLIENT,
        client_id=client.id,
        is_active=client.is_active,
    )
    db.add(user)
    db.commit()

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="client.invited",
        resource_type="client",
        resource_id=client.id,
        details={"email": payload.email},
    )
    db.commit()

    return _client_detail_response(client)


@router.patch("/{client_id}/invite", response_model=ClientDetailResponse)
def reset_client_password(
    client_id: UUID,
    payload: ClientInviteReset,
    owner: Owner,
    db: DbDep,
) -> ClientDetailResponse:
    """Reset the password of a client's login account."""
    client = _get_client_or_404(db, client_id, owner.organization_id)
    if client.user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This client does not have an account",
        )
    client.user.password_hash = hash_password(payload.password)

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="client.password_reset",
        resource_type="client",
        resource_id=client.id,
    )
    db.commit()

    return _client_detail_response(client)
