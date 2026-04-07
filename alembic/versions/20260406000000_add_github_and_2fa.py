"""add github and 2fa fields

Revision ID: 20260406000000
Revises: 20260401000002
Create Date: 2026-04-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260406000000'
down_revision = '20260401000002'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('two_factor_enabled', sa.Boolean(), server_default='1', nullable=True))
    op.add_column('users', sa.Column('email_otp', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('email_otp_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('github_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_github_id'), 'users', ['github_id'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_users_github_id'), table_name='users')
    op.drop_column('users', 'github_id')
    op.drop_column('users', 'email_otp_expires_at')
    op.drop_column('users', 'email_otp')
    op.drop_column('users', 'two_factor_enabled')
