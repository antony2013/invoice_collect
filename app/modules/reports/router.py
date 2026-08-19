from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import DbDep, Owner
from app.models import Client, Invoice, InvoiceStatus
from app.modules.reports.schemas import (
    MonthlySummary,
    ReportSummaryResponse,
    TopClient,
)

router = APIRouter(prefix="/reports", tags=["reports"])

MonthsParam = Annotated[int, Query(ge=1, le=36)]
LimitParam = Annotated[int, Query(ge=1, le=50)]

_TWO_PLACES = Decimal("0.01")


def _dec(value: Decimal | None) -> Decimal:
    return (value if value is not None else Decimal("0")).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )


def _shift_month(day: date, delta: int) -> date:
    total = day.year * 12 + (day.month - 1) + delta
    return date(total // 12, total % 12 + 1, 1)


@router.get("/summary", response_model=ReportSummaryResponse)
def report_summary(
    owner: Owner,
    db: DbDep,
    months: MonthsParam = 6,
    limit: LimitParam = 5,
) -> ReportSummaryResponse:
    """Dashboard summary: status counts, totals, monthly trend, top clients (owner only)."""
    org_id = owner.organization_id

    total_invoices = (
        db.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.organization_id == org_id
            )
        )
        or 0
    )

    total_billed = db.scalar(
        select(func.sum(Invoice.total_amount)).where(
            Invoice.organization_id == org_id,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
    )
    total_billed = _dec(total_billed)

    status_rows = db.execute(
        select(Invoice.status, func.count())
        .where(Invoice.organization_id == org_id)
        .group_by(Invoice.status)
    ).all()
    by_status = {status_: 0 for status_ in InvoiceStatus}
    for status_, count in status_rows:
        by_status[status_] = count

    now = datetime.now(UTC).date()
    first_month = _shift_month(now, -(months - 1))
    month_rows = db.execute(
        select(
            func.strftime("%Y-%m", Invoice.invoice_date).label("year_month"),
            func.count().label("count"),
            func.sum(Invoice.total_amount).label("amount"),
        )
        .where(
            Invoice.organization_id == org_id,
            Invoice.invoice_date >= first_month,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
        .group_by("year_month")
    ).all()
    by_month = {
        row.year_month: (row.count, _dec(row.amount)) for row in month_rows
    }
    monthly: list[MonthlySummary] = []
    cursor = first_month
    while cursor <= now:
        key = f"{cursor.year:04d}-{cursor.month:02d}"
        count, amount = by_month.get(key, (0, Decimal("0.00")))
        monthly.append(MonthlySummary(year_month=key, count=count, amount=amount))
        cursor = _shift_month(cursor, 1)

    client_rows = db.execute(
        select(
            Invoice.client_id,
            func.count().label("invoice_count"),
            func.sum(Invoice.total_amount).label("total_amount"),
        )
        .where(
            Invoice.organization_id == org_id,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
        .group_by(Invoice.client_id)
        .order_by(func.sum(Invoice.total_amount).desc())
        .limit(limit)
    ).all()
    client_names = {
        client.id: client.name
        for client in db.scalars(
            select(Client).where(Client.organization_id == org_id)
        )
    }
    top_clients = [
        TopClient(
            client_id=row.client_id,
            client_name=client_names.get(row.client_id, "Unknown"),
            invoice_count=row.invoice_count,
            total_amount=_dec(row.total_amount),
        )
        for row in client_rows
    ]

    return ReportSummaryResponse(
        total_invoices=total_invoices,
        total_billed=total_billed,
        by_status=by_status,
        monthly=monthly,
        top_clients=top_clients,
    )
