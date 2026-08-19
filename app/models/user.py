from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import OrganizationOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.invoice import Invoice
    from app.models.organization import Organization


class User(UUIDPrimaryKeyMixin, OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_organization_client", "organization_id", "client_id"),
        UniqueConstraint(
            "organization_id",
            "client_id",
            name="uq_users_organization_client",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, length=20, create_constraint=False),
        nullable=False,
        default=UserRole.STAFF,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_id: Mapped[object | None] = mapped_column(
        Uuid, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="users")
    assigned_invoices: Mapped[list[Invoice]] = relationship(
        back_populates="assigned_to"
    )
    client: Mapped[Client | None] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id!s} email={self.email!r} role={self.role.value}>"
