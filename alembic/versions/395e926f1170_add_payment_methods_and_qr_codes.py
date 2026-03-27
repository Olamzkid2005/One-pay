"""add_payment_methods_and_qr_codes

Revision ID: 395e926f1170
Revises: 20260324083520
Create Date: 2026-03-26 07:18:10.083241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '395e926f1170'
down_revision: Union[str, None] = '20260324083520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add QR code columns to transactions table
    op.add_column('transactions', sa.Column('qr_code_payment_url', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('qr_code_virtual_account', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove QR code columns from transactions table
    op.drop_column('transactions', 'qr_code_virtual_account')
    op.drop_column('transactions', 'qr_code_payment_url')
