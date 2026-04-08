"""add webhook idempotency table

Revision ID: 20260407000000
Revises: 20260406000000
Create Date: 2026-04-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20260407000000'
down_revision = '20260406000000'
branch_labels = None
depends_on = None

def upgrade():
    # Create webhook_idempotency table
    op.create_table(
        'webhook_idempotency',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('tx_ref', sa.String(100), nullable=True),
    )
    
    # Create index on processed_at for cleanup queries
    op.create_index('ix_webhook_idempotency_processed', 'webhook_idempotency', ['processed_at'])

def downgrade():
    # Drop index first
    op.drop_index('ix_webhook_idempotency_processed', table_name='webhook_idempotency')
    
    # Drop table
    op.drop_table('webhook_idempotency')
