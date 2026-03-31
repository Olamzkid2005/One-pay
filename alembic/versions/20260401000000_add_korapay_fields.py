"""add korapay fields

Revision ID: 20260401000000
Revises: 20260329140000
Create Date: 2026-04-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260401000000'
down_revision = '20260329140000'
branch_labels = None
depends_on = None


def upgrade():
    """Add KoraPay-specific fields to transactions table."""
    # Add KoraPay-specific columns (all nullable for backward compatibility)
    op.add_column('transactions', sa.Column('payment_provider_reference', sa.String(length=100), nullable=True))
    op.add_column('transactions', sa.Column('provider_fee', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('transactions', sa.Column('provider_vat', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('transactions', sa.Column('provider_transaction_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('transactions', sa.Column('payer_bank_details', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('failure_reason', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('provider_status', sa.String(length=50), nullable=True))
    op.add_column('transactions', sa.Column('bank_code', sa.String(length=10), nullable=True))
    op.add_column('transactions', sa.Column('virtual_account_expiry', sa.DateTime(timezone=True), nullable=True))
    
    # Create indexes for common queries
    op.create_index('idx_payment_provider_reference', 'transactions', ['payment_provider_reference'], unique=False)
    op.create_index('idx_provider_transaction_date', 'transactions', ['provider_transaction_date'], unique=False)


def downgrade():
    """Remove KoraPay-specific fields from transactions table."""
    # Drop indexes first
    op.drop_index('idx_provider_transaction_date', table_name='transactions')
    op.drop_index('idx_payment_provider_reference', table_name='transactions')
    
    # Drop columns
    op.drop_column('transactions', 'virtual_account_expiry')
    op.drop_column('transactions', 'bank_code')
    op.drop_column('transactions', 'provider_status')
    op.drop_column('transactions', 'failure_reason')
    op.drop_column('transactions', 'payer_bank_details')
    op.drop_column('transactions', 'provider_transaction_date')
    op.drop_column('transactions', 'provider_vat')
    op.drop_column('transactions', 'provider_fee')
    op.drop_column('transactions', 'payment_provider_reference')
