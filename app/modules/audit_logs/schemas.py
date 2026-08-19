from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class AuditLogListEnvelope(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
