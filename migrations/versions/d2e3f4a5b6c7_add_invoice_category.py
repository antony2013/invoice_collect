"""add invoice category

Revision ID: d2e3f4a5b6c7
Revises: c1f2a3b4d5e6
Create Date: 2026-08-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1f2a3b4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('invoices') as batch_op:
        batch_op.add_column(
            sa.Column(
                'category',
                sa.String(30),
                nullable=False,
                server_default='OTHER_DOCUMENT',
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('invoices') as batch_op:
        batch_op.drop_column('category')
