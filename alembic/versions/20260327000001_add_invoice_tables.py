"""add_invoice_tables

Revision ID: 20260327000001
Revises: 395e926f1170
Create Date: 2026-03-27 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260327000001'
down_revision: Union[str, None] = '395e926f1170'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create invoice_settings table
    op.create_table(
        'invoice_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('business_name', sa.String(length=255), nullable=True),
        sa.Column('business_address', sa.Text(), nullable=True),
        sa.Column('business_tax_id', sa.String(length=100), nullable=True),
        sa.Column('business_logo_url', sa.String(length=500), nullable=True),
        sa.Column('default_payment_terms', sa.Text(), nullable=True, server_default='Payment due upon receipt'),
        sa.Column('auto_send_email', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_invoice_settings_user_id', 'invoice_settings', ['user_id'], unique=False)

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(length=20), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True, server_default='NGN'),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('customer_email', sa.String(length=255), nullable=True),
        sa.Column('customer_phone', sa.String(length=20), nullable=True),
        sa.Column('business_name', sa.String(length=255), nullable=True),
        sa.Column('business_address', sa.Text(), nullable=True),
        sa.Column('business_tax_id', sa.String(length=100), nullable=True),
        sa.Column('business_logo_url', sa.String(length=500), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('DRAFT', 'SENT', 'PAID', 'EXPIRED', 'CANCELLED', name='invoicestatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_attempts', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('email_last_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number'),
        sa.UniqueConstraint('transaction_id')
    )
    
    # Create indexes for invoices table
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=False)
    op.create_index('ix_invoices_transaction', 'invoices', ['transaction_id'], unique=False)
    op.create_index('ix_invoices_user_created', 'invoices', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_invoices_user_status', 'invoices', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    # Drop invoices table and indexes
    op.drop_index('ix_invoices_user_status', table_name='invoices')
    op.drop_index('ix_invoices_user_created', table_name='invoices')
    op.drop_index('ix_invoices_transaction', table_name='invoices')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.drop_table('invoices')
    
    # Drop invoice_settings table and indexes
    op.drop_index('ix_invoice_settings_user_id', table_name='invoice_settings')
    op.drop_table('invoice_settings')
    
    # Drop enum type (PostgreSQL specific, SQLite ignores this)
    op.execute('DROP TYPE IF EXISTS invoicestatus')
