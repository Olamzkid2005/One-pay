"""add webhook blacklist

Revision ID: 20260329135018
Revises: 20260327000001
Create Date: 2026-03-29 13:50:18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329135018'
down_revision = '20260327000001'
branch_labels = None
depends_on = None


def upgrade():
    """Create webhook_blacklist table for SSRF protection."""
    op.create_table(
        'webhook_blacklist',
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('url')
    )
    
    # Create index on blacklisted_at for cleanup queries
    op.create_index('ix_webhook_blacklist_blacklisted_at', 'webhook_blacklist', ['blacklisted_at'])


def downgrade():
    """Drop webhook_blacklist table."""
    op.drop_index('ix_webhook_blacklist_blacklisted_at', table_name='webhook_blacklist')
    op.drop_table('webhook_blacklist')
