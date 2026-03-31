"""add api_keys table

Revision ID: 20260401000002
Revises: 20260401000001
Create Date: 2026-04-01 00:00:02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260401000002'
down_revision = '20260401000001'
branch_labels = None
depends_on = None


def upgrade():
    """Create api_keys table for API key authentication."""
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))"), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('key_hash', name='uq_api_keys_key_hash')
    )
    
    # Create indexes for common queries
    op.create_index('idx_api_keys_user_id', 'api_keys', ['user_id'], unique=False)
    op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'], unique=False)


def downgrade():
    """Drop api_keys table."""
    op.drop_index('idx_api_keys_key_hash', table_name='api_keys')
    op.drop_index('idx_api_keys_user_id', table_name='api_keys')
    op.drop_table('api_keys')
