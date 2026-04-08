"""add audit log indexes

Revision ID: 20260408000002
Revises: 20260408000001
Create Date: 2026-04-08 00:00:02.000000

"""
from alembic import op

revision = '20260408000002'
down_revision = '20260408000001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])


def downgrade():
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
