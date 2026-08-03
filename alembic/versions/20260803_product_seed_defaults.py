"""align product ORM defaults with existing stock columns

Revision ID: 20260803_product_seed_defaults
Revises: 20260803_supplier_payments
"""

from alembic import op
import sqlalchemy as sa

revision = "20260803_product_seed_defaults"
down_revision = "20260803_supplier_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("products", "minimum_stock", existing_type=sa.Numeric(12, 2), server_default="0")
    op.alter_column("products", "reorder_level", existing_type=sa.Numeric(12, 2), server_default="0")
    op.alter_column("products", "maximum_stock", existing_type=sa.Numeric(12, 2), server_default="0")
    op.alter_column("products", "lead_time_days", existing_type=sa.Integer(), server_default="0")


def downgrade():
    op.alter_column("products", "lead_time_days", existing_type=sa.Integer(), server_default=None)
    op.alter_column("products", "maximum_stock", existing_type=sa.Numeric(12, 2), server_default=None)
    op.alter_column("products", "reorder_level", existing_type=sa.Numeric(12, 2), server_default=None)
    op.alter_column("products", "minimum_stock", existing_type=sa.Numeric(12, 2), server_default=None)
