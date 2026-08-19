from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import InvoiceStatus


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class InvoiceSummary(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_date: date
    status: InvoiceStatus
    total_amount: Decimal
    assigned_to_id: uuid.UUID | None
    assigned_to_name: str | None


class ClientListResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr | None
    phone: str | None
    address: str | None
    is_active: bool
    created_at: datetime
    invoice_count: int
    total_billed: Decimal
    account_email: EmailStr | None


class ClientDetailResponse(ClientListResponse):
    notes: str | None
    updated_at: datetime
    invoices: list[InvoiceSummary]


class ClientProfileResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr | None
    phone: str | None
    address: str | None
    created_at: datetime


class ClientInviteRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ClientInviteReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)
