"""add google oauth fields

Revision ID: 20260329140000
Revises: 20260329135018
Create Date: 2026-03-29 14:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260329140000'
down_revision = '20260329135018'
branch_labels = None
depends_on = None


def upgrade():
    """Add Google OAuth fields to users table."""
    # Add OAuth provider columns
    op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('profile_picture_url', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('full_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('auth_provider', sa.String(length=20), nullable=False, server_default='traditional'))
    
    # Create unique index on google_id for fast lookups and constraint enforcement
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)


def downgrade():
    """Remove Google OAuth fields from users table."""
    op.drop_index('ix_users_google_id', table_name='users')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'profile_picture_url')
    op.drop_column('users', 'google_id')
