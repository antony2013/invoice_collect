"""add client link to users

Revision ID: c1f2a3b4d5e6
Revises: ab5b5a3249a5
Create Date: 2026-08-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f2a3b4d5e6'
down_revision: Union[str, Sequence[str], None] = 'ab5b5a3249a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.Uuid(), nullable=True))
        batch_op.create_index('ix_users_organization_client', ['organization_id', 'client_id'], unique=False)
        batch_op.create_unique_constraint('uq_users_organization_client', ['organization_id', 'client_id'])
        batch_op.create_foreign_key('fk_users_client_id_clients', 'clients', ['client_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_client_id_clients', type_='foreignkey')
        batch_op.drop_constraint('uq_users_organization_client', type_='unique')
        batch_op.drop_index('ix_users_organization_client')
        batch_op.drop_column('client_id')
