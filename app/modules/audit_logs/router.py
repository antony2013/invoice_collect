from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import DbDep, Owner
from app.core.params import PageParam, PageSizeParam
from app.models import AuditLog
from app.modules.audit_logs.schemas import AuditLogListEnvelope, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

ActionFilter = Annotated[str | None, Query()]
ResourceTypeFilter = Annotated[str | None, Query()]
ResourceIdFilter = Annotated[UUID | None, Query()]
ActorIdFilter = Annotated[UUID | None, Query()]
CreatedAfterFilter = Annotated[datetime | None, Query()]
CreatedBeforeFilter = Annotated[datetime | None, Query()]


def _to_response(entry: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=entry.id,
        actor_id=entry.actor_id,
        actor_name=entry.actor.full_name if entry.actor else None,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        details=entry.details,
        ip_address=entry.ip_address,
        created_at=entry.created_at,
    )


@router.get("", response_model=AuditLogListEnvelope)
def list_audit_logs(
    owner: Owner,
    db: DbDep,
    action: ActionFilter = None,
    resource_type: ResourceTypeFilter = None,
    resource_id: ResourceIdFilter = None,
    actor_id: ActorIdFilter = None,
    created_after: CreatedAfterFilter = None,
    created_before: CreatedBeforeFilter = None,
    page: PageParam = 1,
    page_size: PageSizeParam = 20,
) -> AuditLogListEnvelope:
    """List organization audit logs with optional filters (owner only)."""
    org_id = owner.organization_id
    filters = [AuditLog.organization_id == org_id]
    if action is not None:
        filters.append(AuditLog.action == action)
    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if created_after is not None:
        filters.append(AuditLog.created_at >= created_after)
    if created_before is not None:
        filters.append(AuditLog.created_at <= created_before)

    total = (
        db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    )
    entries = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AuditLogListEnvelope(
        items=[_to_response(entry) for entry in entries],
        total=total,
        page=page,
        page_size=page_size,
    )
