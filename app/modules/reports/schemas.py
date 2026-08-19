from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import InvoiceStatus


class StatusCount(BaseModel):
    status: InvoiceStatus
    count: int


class MonthlySummary(BaseModel):
    year_month: str
    count: int
    amount: Decimal


class TopClient(BaseModel):
    client_id: uuid.UUID
    client_name: str
    invoice_count: int
    total_amount: Decimal


class ReportSummaryResponse(BaseModel):
    total_invoices: int
    total_billed: Decimal
    by_status: dict[InvoiceStatus, int]
    monthly: list[MonthlySummary]
    top_clients: list[TopClient]
