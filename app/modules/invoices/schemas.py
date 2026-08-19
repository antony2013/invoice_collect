from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import InvoiceStatus


class InvoiceItemPayload(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    content_type: str | None
    size_bytes: int
    uploaded_by_name: str | None
    created_at: datetime


class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    invoice_number: str | None = Field(default=None, min_length=1, max_length=50)
    invoice_date: date
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=2000)
    assigned_to_id: uuid.UUID | None = None
    items: list[InvoiceItemPayload] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def _uppercase_currency(cls, value: str) -> str:
        return value.upper()


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = Field(default=None, max_length=2000)
    assigned_to_id: uuid.UUID | None = None
    status: InvoiceStatus | None = None
    items: list[InvoiceItemPayload] | None = None

    @field_validator("currency")
    @classmethod
    def _uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class InvoiceListResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    invoice_number: str
    invoice_date: date
    status: InvoiceStatus
    currency: str
    total_amount: Decimal
    assigned_to_id: uuid.UUID | None
    assigned_to_name: str | None
    created_at: datetime


class InvoiceDetailResponse(InvoiceListResponse):
    notes: str | None
    updated_at: datetime
    items: list[InvoiceItemResponse]
    files: list[InvoiceFileResponse]


class InvoiceListEnvelope(BaseModel):
    items: list[InvoiceListResponse]
    total: int
    page: int
    page_size: int
