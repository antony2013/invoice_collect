from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow


class RevokedToken(UUIDPrimaryKeyMixin, Base):
    """JWT identifiers that have been invalidated (e.g. on logout)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RevokedToken jti={self.jti!r}>"
