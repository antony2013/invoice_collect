from __future__ import annotations

import enum


class UserRole(enum.StrEnum):
    """User roles within an organization."""

    OWNER = "OWNER"
    STAFF = "STAFF"
    CLIENT = "CLIENT"


class InvoiceStatus(enum.StrEnum):
    """Lifecycle states for an invoice."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REVIEW = "REVIEW"
    CANCELLED = "CANCELLED"
