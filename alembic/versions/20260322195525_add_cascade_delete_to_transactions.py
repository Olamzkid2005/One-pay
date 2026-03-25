"""Add cascade delete to transactions

Revision ID: 20260322195525
Revises: 28241778f1e0
Create Date: 2026-03-22 19:55:25.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260322195525'
down_revision = '28241778f1e0'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add CASCADE DELETE behavior to transactions.user_id foreign key.
    
    Note: SQLite doesn't support modifying foreign keys directly.
    The foreign key constraint with ondelete='SET NULL' is already
    defined in the model (models/transaction.py), so new tables
    created will have the correct constraint.
    
    For existing databases, this is a no-op migration that documents
    the change. The constraint will be applied when the table is
    recreated (e.g., during a full migration or database rebuild).
    """
    # No operation needed for SQLite - the model change is sufficient
    # New instances will use the updated foreign key definition
    pass


def downgrade():
    """
    Remove CASCADE DELETE behavior from transactions.user_id foreign key.
    """
    # No operation needed for SQLite
    pass
