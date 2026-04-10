"""add exchange rates table for multi-currency support

Revision ID: 20260410000002
Revises: 20260410000001
Create Date: 2026-04-10 00:00:02

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260410000002'
down_revision = '20260410000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create exchange_rates table for multi-currency support."""
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_currency', sa.String(length=3), nullable=False),
        sa.Column('to_currency', sa.String(length=3), nullable=False),
        sa.Column('rate', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency', 'to_currency', name='uix_currency_pair')
    )

    # Create index for common queries
    op.create_index('ix_exchange_rates_from_currency', 'exchange_rates', ['from_currency'], unique=False)
    op.create_index('ix_exchange_rates_to_currency', 'exchange_rates', ['to_currency'], unique=False)


def downgrade() -> None:
    """Drop exchange_rates table."""
    op.drop_index('ix_exchange_rates_to_currency', table_name='exchange_rates')
    op.drop_index('ix_exchange_rates_from_currency', table_name='exchange_rates')
    op.drop_table('exchange_rates')
