from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select

from app.core.audit import write_audit_log
from app.core.deps import CurrentUser, DbDep
from app.core.minio import MinioDep
from app.models import Client, Invoice, InvoiceFile, User, UserRole
from app.models.base import utcnow
from app.models.enums import InvoiceStatus
from app.modules.clients.schemas import ClientProfileResponse
from app.modules.invoices.files import (
    MAX_UPLOAD_BYTES,
    UploadDep,
    _object_key,
    _sanitize_filename,
)
from app.modules.invoices.router import (
    _file_response,
    _invoice_number,
    _to_detail_response,
    _to_list_response,
)
from app.modules.invoices.schemas import (
    InvoiceDetailResponse,
    InvoiceFileResponse,
    InvoiceListEnvelope,
)

router = APIRouter(prefix="/clients/me", tags=["clients"])


def _get_client_or_403(current_user: User) -> Client:
    """Resolve the authenticated client record or reject non-client callers."""
    if current_user.role is not UserRole.CLIENT or current_user.client_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client accounts can access this resource",
        )
    client = current_user.client
    if client is None or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client account is inactive",
        )
    return client


def _get_own_invoice_or_404(db: DbDep, client: Client, invoice_id: UUID) -> Invoice:
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.client_id == client.id,
            Invoice.organization_id == client.organization_id,
        )
    )
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return invoice


def _get_own_file_or_404(
    db: DbDep,
    client: Client,
    invoice: Invoice,
    file_id: UUID,
) -> InvoiceFile:
    file = db.scalar(
        select(InvoiceFile).where(
            InvoiceFile.id == file_id,
            InvoiceFile.invoice_id == invoice.id,
            InvoiceFile.organization_id == client.organization_id,
        )
    )
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return file


async def _store_file(
    db: DbDep,
    *,
    client: Client,
    invoice: Invoice,
    current_user: User,
    storage: MinioDep,
    upload: UploadFile,
) -> InvoiceFile:
    """Validate, store, and register an uploaded file for a client invoice."""
    data = await upload.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 25 MB size limit",
        )

    original_name = upload.filename or "unnamed"
    object_key = _object_key(
        client.organization_id,
        invoice,
        _sanitize_filename(original_name),
    )
    storage.upload_object(
        object_key=object_key,
        data=data,
        content_type=upload.content_type,
    )

    file = InvoiceFile(
        organization_id=client.organization_id,
        invoice_id=invoice.id,
        original_name=original_name,
        object_key=object_key,
        content_type=upload.content_type,
        size_bytes=len(data),
        uploaded_by_id=current_user.id,
    )
    db.add(file)
    return file


@router.get("", response_model=ClientProfileResponse)
def get_my_profile(current_user: CurrentUser, db: DbDep) -> ClientProfileResponse:
    """Return the client profile for the authenticated client user."""
    client = _get_client_or_403(current_user)
    return ClientProfileResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        address=client.address,
        created_at=client.created_at,
    )


@router.get("/invoices", response_model=InvoiceListEnvelope)
def list_my_invoices(current_user: CurrentUser, db: DbDep) -> InvoiceListEnvelope:
    """List the authenticated client's own invoices."""
    client = _get_client_or_403(current_user)
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.client_id == client.id)
        .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
    ).all()
    return InvoiceListEnvelope(
        items=[_to_list_response(db, inv) for inv in invoices],
        total=len(invoices),
        page=1,
        page_size=len(invoices),
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
def get_my_invoice(
    invoice_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> InvoiceDetailResponse:
    """Return one of the authenticated client's invoices."""
    client = _get_client_or_403(current_user)
    invoice = _get_own_invoice_or_404(db, client, invoice_id)
    return _to_detail_response(db, invoice)


@router.post(
    "/invoices/upload",
    response_model=InvoiceDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_my_invoice(
    current_user: CurrentUser,
    db: DbDep,
    storage: MinioDep,
    upload: UploadDep,
    notes: Annotated[str | None, Form()] = None,
) -> InvoiceDetailResponse:
    """Create a PENDING invoice for the client and attach the uploaded file."""
    client = _get_client_or_403(current_user)
    invoice = Invoice(
        organization_id=client.organization_id,
        client_id=client.id,
        assigned_to_id=None,
        invoice_number=_invoice_number(),
        invoice_date=utcnow().date(),
        currency="USD",
        notes=notes,
        status=InvoiceStatus.PENDING,
        total_amount=Decimal("0"),
    )
    db.add(invoice)
    db.flush()
    file = await _store_file(
        db,
        client=client,
        invoice=invoice,
        current_user=current_user,
        storage=storage,
        upload=upload,
    )
    db.commit()
    db.expire(invoice)

    write_audit_log(
        db,
        organization_id=client.organization_id,
        actor_id=current_user.id,
        action="invoice.created",
        resource_type="invoice",
        resource_id=invoice.id,
    )
    write_audit_log(
        db,
        organization_id=client.organization_id,
        actor_id=current_user.id,
        action="invoice_file.uploaded",
        resource_type="invoice_file",
        resource_id=file.id,
        details={"original_name": file.original_name, "size_bytes": file.size_bytes},
    )
    db.commit()

    return _to_detail_response(db, invoice)


@router.post(
    "/invoices/{invoice_id}/files",
    response_model=InvoiceFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_file_to_my_invoice(
    invoice_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
    storage: MinioDep,
    upload: UploadDep,
) -> InvoiceFileResponse:
    """Attach another file to one of the authenticated client's invoices."""
    client = _get_client_or_403(current_user)
    invoice = _get_own_invoice_or_404(db, client, invoice_id)
    file = await _store_file(
        db,
        client=client,
        invoice=invoice,
        current_user=current_user,
        storage=storage,
        upload=upload,
    )
    db.commit()
    db.refresh(file)

    write_audit_log(
        db,
        organization_id=client.organization_id,
        actor_id=current_user.id,
        action="invoice_file.uploaded",
        resource_type="invoice_file",
        resource_id=file.id,
        details={"original_name": file.original_name, "size_bytes": file.size_bytes},
    )
    db.commit()

    return _file_response(file)


@router.get("/invoices/{invoice_id}/files/{file_id}/download")
def download_my_invoice_file(
    invoice_id: UUID,
    file_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
    storage: MinioDep,
) -> Response:
    """Download a file belonging to one of the authenticated client's invoices."""
    client = _get_client_or_403(current_user)
    invoice = _get_own_invoice_or_404(db, client, invoice_id)
    file = _get_own_file_or_404(db, client, invoice, file_id)
    try:
        data = storage.get_object(object_key=file.object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        ) from exc

    return Response(
        content=data,
        media_type=file.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(file.original_name)}"
            )
        },
    )
