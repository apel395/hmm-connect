"""Add purchase order subtotal for item-level PPN totals.

Revision ID: 20260814_purchase_order_subtotal
Revises: 20260814_purchasing_approval_roles
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_purchase_order_subtotal"
down_revision = "20260814_purchasing_approval_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchase_orders", sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.execute("UPDATE purchase_orders SET subtotal = total_amount WHERE subtotal = 0")


def downgrade():
    op.drop_column("purchase_orders", "subtotal")
