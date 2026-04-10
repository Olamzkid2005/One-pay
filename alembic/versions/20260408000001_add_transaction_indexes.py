"""add transaction indexes

Revision ID: 20260408000001
Revises: 20260407000000
Create Date: 2026-04-08 00:00:01.000000

"""
from alembic import op

revision = '20260408000001'
down_revision = '20260407000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_transactions_created_at', 'transactions', ['created_at'])
    op.create_index('ix_transactions_status', 'transactions', ['status'])
    op.create_index('ix_transactions_user_created', 'transactions', ['user_id', 'created_at'])
    op.create_index('ix_transactions_user_status', 'transactions', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_transactions_user_status', table_name='transactions')
    op.drop_index('ix_transactions_user_created', table_name='transactions')
    op.drop_index('ix_transactions_status', table_name='transactions')
    op.drop_index('ix_transactions_created_at', table_name='transactions')
