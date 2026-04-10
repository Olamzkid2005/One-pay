"""add invoice reminder settings for payment reminders

Revision ID: 20260410000005
Revises: 20260410000004
Create Date: 2026-04-10 00:00:05

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260410000005'
down_revision = '20260410000004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add reminder settings columns to invoice_settings table."""
    op.add_column('invoice_settings', sa.Column('reminder_enabled', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('invoice_settings', sa.Column('reminder_days_before_due', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('invoice_settings', sa.Column('reminder_days_overdue', sa.Integer(), nullable=False, server_default='7'))
    op.add_column('invoice_settings', sa.Column('reminder_max_attempts', sa.Integer(), nullable=False, server_default='3'))


def downgrade() -> None:
    """Remove reminder settings columns from invoice_settings table."""
    op.drop_column('invoice_settings', 'reminder_max_attempts')
    op.drop_column('invoice_settings', 'reminder_days_overdue')
    op.drop_column('invoice_settings', 'reminder_days_before_due')
    op.drop_column('invoice_settings', 'reminder_enabled')
