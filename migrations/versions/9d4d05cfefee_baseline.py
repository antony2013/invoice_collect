"""baseline

Revision ID: 9d4d05cfefee
Revises: 
Create Date: 2026-08-15 09:53:49.075367

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '9d4d05cfefee'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
