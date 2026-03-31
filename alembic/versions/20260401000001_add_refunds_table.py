"""add refunds table

Revision ID: 20260401000001
Revises: 20260401000000
Create Date: 2026-04-01 00:00:01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260401000001'
down_revision = '20260401000000'
branch_labels = None
depends_on = None


def upgrade():
    """Create refunds table for tracking refund operations."""
    op.create_table(
        'refunds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('refund_reference', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='NGN'),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('provider_refund_id', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('refund_reference', name='uq_refunds_refund_reference')
    )
    
    # Create indexes for common queries
    op.create_index('idx_refunds_transaction_id', 'refunds', ['transaction_id'], unique=False)
    op.create_index('idx_refunds_status', 'refunds', ['status'], unique=False)
    op.create_index('idx_refunds_created_at', 'refunds', ['created_at'], unique=False)


def downgrade():
    """Drop refunds table."""
    op.drop_index('idx_refunds_created_at', table_name='refunds')
    op.drop_index('idx_refunds_status', table_name='refunds')
    op.drop_index('idx_refunds_transaction_id', table_name='refunds')
    op.drop_table('refunds')
