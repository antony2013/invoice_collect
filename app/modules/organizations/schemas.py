from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    staff_count: int
    client_count: int
    invoice_count: int


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
