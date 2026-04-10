"""add audit logs composite indexes

Revision ID: 20260410000001
Revises: 20260410000000
Create Date: 2026-04-10 00:00:01.000000

"""
from alembic import op

revision = '20260410000001'
down_revision = '20260410000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for user_id and created_at on audit_logs
    # This improves performance for queries filtering by user and time range
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
