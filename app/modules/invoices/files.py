from __future__ import annotations

import re
import uuid
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, UploadFile, status

from app.core.audit import write_audit_log
from app.core.crud import get_owned_or_404
from app.core.deps import CurrentUser, DbDep, Owner
from app.core.minio import MinioDep
from app.core.ratelimit import UploadRateLimit
from app.models import Invoice, InvoiceFile, User, UserRole
from app.modules.invoices.router import _file_response
from app.modules.invoices.schemas import InvoiceFileResponse

router = APIRouter(prefix="/invoices", tags=["invoices"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

UploadDep = Annotated[UploadFile, File(...)]

_SAFE_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")

_ALLOWED_UPLOAD_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/heic",
        "image/heif",
    }
)

# (offset, bytes, sniffed content-type) — validated against the declared one.
_MAGIC_SIGNATURES: tuple[tuple[int, bytes, str], ...] = (
    (0, b"%PDF-", "application/pdf"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"GIF87a", "image/gif"),
    (0, b"GIF89a", "image/gif"),
    (0, b"RIFF", "image/webp"),
)


def _validate_upload(content_type: str | None, data: bytes) -> None:
    """Reject unsupported content types and files whose magic bytes disagree."""
    declared = (content_type or "").split(";")[0].strip().lower()
    if declared and declared not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: PDF and image files.",
        )

    head = data[:12]
    matched: list[str] = [
        sniffed for offset, sig, sniffed in _MAGIC_SIGNATURES
        if head[offset : offset + len(sig)] == sig
    ]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match a supported format.",
        )
    magic_checked = "image/heic" not in declared and "image/heif" not in declared
    if declared and magic_checked and declared not in matched:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Declared type does not match file content.",
        )


def _sanitize_filename(filename: str) -> str:
    cleaned = _SAFE_NAME_PATTERN.sub("_", filename).strip("._")
    return cleaned[:150] or "file"


def _object_key(organization_id: UUID, invoice: Invoice, safe_name: str) -> str:
    return (
        f"organizations/{organization_id}"
        f"/clients/{invoice.client_id}"
        f"/invoices/{invoice.invoice_date.year}/{invoice.invoice_date.month:02d}"
        f"/{invoice.id}/{uuid.uuid4().hex}-{safe_name}"
    )


def _get_file_or_404(
    db: DbDep,
    invoice_id: UUID,
    file_id: UUID,
    organization_id: UUID,
) -> InvoiceFile:
    invoice = get_owned_or_404(
        db,
        Invoice,
        record_id=invoice_id,
        organization_id=organization_id,
        detail="Invoice not found",
    )
    file = get_owned_or_404(
        db,
        InvoiceFile,
        record_id=file_id,
        organization_id=organization_id,
        detail="File not found",
    )
    if file.invoice_id != invoice.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return file


def _require_file_access(current_user: User, invoice: Invoice) -> None:
    """Only the staff member assigned to an invoice may touch its files."""
    if current_user.role is UserRole.OWNER:
        return
    if invoice.assigned_to_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff can only work on invoices assigned to them",
        )


@router.post(
    "/{invoice_id}/files",
    response_model=InvoiceFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_invoice_file(
    invoice_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
    storage: MinioDep,
    upload: UploadDep,
    _: UploadRateLimit,
) -> InvoiceFileResponse:
    """Upload an invoice file to object storage and register it."""
    org_id = current_user.organization_id
    invoice = get_owned_or_404(
        db,
        Invoice,
        record_id=invoice_id,
        organization_id=org_id,
        detail="Invoice not found",
    )
    _require_file_access(current_user, invoice)

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
    _validate_upload(upload.content_type, data)

    original_name = upload.filename or "unnamed"
    object_key = _object_key(org_id, invoice, _sanitize_filename(original_name))
    storage.upload_object(
        object_key=object_key,
        data=data,
        content_type=upload.content_type,
    )

    file = InvoiceFile(
        organization_id=org_id,
        invoice_id=invoice.id,
        original_name=original_name,
        object_key=object_key,
        content_type=upload.content_type,
        size_bytes=len(data),
        uploaded_by_id=current_user.id,
    )
    db.add(file)
    db.flush()
    db.refresh(file)

    write_audit_log(
        db,
        organization_id=org_id,
        actor_id=current_user.id,
        action="invoice_file.uploaded",
        resource_type="invoice_file",
        resource_id=file.id,
        details={"original_name": original_name, "size_bytes": len(data)},
    )
    db.commit()

    return _file_response(file)


@router.get("/{invoice_id}/files/{file_id}/download")
def download_invoice_file(
    invoice_id: UUID,
    file_id: UUID,
    current_user: CurrentUser,
    db: DbDep,
    storage: MinioDep,
) -> Response:
    """Download an invoice file from object storage."""
    file = _get_file_or_404(db, invoice_id, file_id, current_user.organization_id)
    _require_file_access(current_user, file.invoice)
    try:
        data = storage.get_object(object_key=file.object_key)
    except HTTPException:
        raise
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
                f'attachment; filename*=UTF-8\'\'{quote(file.original_name)}'
            )
        },
    )


@router.delete("/{invoice_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice_file(
    invoice_id: UUID,
    file_id: UUID,
    owner: Owner,
    db: DbDep,
    storage: MinioDep,
) -> None:
    """Delete an invoice file from object storage and the registry (owner only)."""
    file = _get_file_or_404(db, invoice_id, file_id, owner.organization_id)
    try:
        storage.remove_object(object_key=file.object_key)
    except Exception:
        pass

    write_audit_log(
        db,
        organization_id=owner.organization_id,
        actor_id=owner.id,
        action="invoice_file.deleted",
        resource_type="invoice_file",
        resource_id=file.id,
        details={"original_name": file.original_name},
    )
    db.delete(file)
    db.commit()
