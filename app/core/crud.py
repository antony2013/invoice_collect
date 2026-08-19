from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


def get_owned_or_404(
    db: Session,
    model: type[ModelT],
    *,
    record_id: UUID,
    organization_id: UUID,
    detail: str = "Resource not found",
) -> ModelT:
    """Fetch an organization-owned record or raise 404.

    Multi-tenant guard: the record must belong to the caller's organization.
    """
    record = db.scalar(
        select(model).where(
            model.id == record_id,  # type: ignore[attr-defined]
            model.organization_id == organization_id,  # type: ignore[attr-defined]
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return record
