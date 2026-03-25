"""migrate_to_bcrypt

Revision ID: 20260324083520
Revises: 20260322195525
Create Date: 2026-03-24 08:35:20

This migration doesn't modify the database schema.
Existing werkzeug password hashes will continue to work via the fallback
in User.check_password(). New passwords and password resets will use bcrypt.

Users will be automatically migrated to bcrypt when they next log in.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260324083520'
down_revision: Union[str, None] = '20260322195525'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No schema changes needed - bcrypt hashes fit in existing VARCHAR(255)
    # Existing werkzeug hashes remain valid via fallback in User.check_password()
    pass


def downgrade() -> None:
    # No schema changes to revert
    pass
