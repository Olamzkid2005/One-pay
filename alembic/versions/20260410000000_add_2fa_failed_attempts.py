"""add 2fa failed attempts tracking

Revision ID: 20260410000000
Revises: 20260406000000
Create Date: 2026-04-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260410000000'
down_revision = '20260406000000'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('failed_2fa_attempts', sa.Integer(), server_default='0', nullable=True))
    op.add_column('users', sa.Column('twofa_locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'twofa_locked_until')
    op.drop_column('users', 'failed_2fa_attempts')
