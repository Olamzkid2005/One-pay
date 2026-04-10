"""add invoice templates table for custom invoice designs

Revision ID: 20260410000003
Revises: 20260410000002
Create Date: 2026-04-10 00:00:03

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260410000003'
down_revision = '20260410000002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create invoice_templates table for custom invoice designs."""
    op.create_table(
        'invoice_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('html_template', sa.Text(), nullable=False),
        sa.Column('css_styles', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Create indexes for common queries
    op.create_index('ix_invoice_templates_user_id', 'invoice_templates', ['user_id'], unique=False)
    op.create_index('ix_invoice_templates_is_default', 'invoice_templates', ['is_default'], unique=False)


def downgrade() -> None:
    """Drop invoice_templates table."""
    op.drop_index('ix_invoice_templates_is_default', table_name='invoice_templates')
    op.drop_index('ix_invoice_templates_user_id', table_name='invoice_templates')
    op.drop_table('invoice_templates')
