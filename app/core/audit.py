from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    organization_id: UUID,
    action: str,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    details: dict[str, object] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create and stage an audit log entry (caller must commit)."""
    entry = AuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry
