"""create report requests table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-20 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'report_requests',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.Uuid(), sa.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('owner_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_report_requests_organization_id', 'report_requests', ['organization_id'])
    op.create_index('ix_report_requests_client_id', 'report_requests', ['client_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_report_requests_client_id', table_name='report_requests')
    op.drop_index('ix_report_requests_organization_id', table_name='report_requests')
    op.drop_table('report_requests')
