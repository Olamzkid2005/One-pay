"""add recurring invoices table for scheduled invoice generation

Revision ID: 20260410000004
Revises: 20260410000003
Create Date: 2026-04-10 00:00:04

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260410000004'
down_revision = '20260410000003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create recurring_invoices table for scheduled invoice generation."""
    op.create_table(
        'recurring_invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_email', sa.String(length=255), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=True),
        sa.Column('customer_phone', sa.String(length=20), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='NGN'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('frequency', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_invoice_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Create indexes for common queries
    op.create_index('ix_recurring_invoices_user_id', 'recurring_invoices', ['user_id'], unique=False)
    op.create_index('ix_recurring_invoices_next_invoice_date', 'recurring_invoices', ['next_invoice_date'], unique=False)
    op.create_index('ix_recurring_invoices_is_active', 'recurring_invoices', ['is_active'], unique=False)


def downgrade() -> None:
    """Drop recurring_invoices table."""
    op.drop_index('ix_recurring_invoices_is_active', table_name='recurring_invoices')
    op.drop_index('ix_recurring_invoices_next_invoice_date', table_name='recurring_invoices')
    op.drop_index('ix_recurring_invoices_user_id', table_name='recurring_invoices')
    op.drop_table('recurring_invoices')
