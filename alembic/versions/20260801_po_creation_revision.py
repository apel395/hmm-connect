"""revise PO creation fields and remove receipt tolerance

Revision ID: 20260801_po_creation
Revises: 20260801_document_sequences
"""
from alembic import op
import sqlalchemy as sa

revision = "20260801_po_creation"
down_revision = "20260801_document_sequences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchase_orders", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("purchase_orders", sa.Column("location_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_purchase_orders_department", "purchase_orders", "departments", ["department_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_purchase_orders_location", "purchase_orders", "locations", ["location_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_purchase_orders_department_id", "purchase_orders", ["department_id"])
    op.create_index("ix_purchase_orders_location_id", "purchase_orders", ["location_id"])
    op.add_column("purchase_order_items", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("purchase_order_items", sa.Column("uom", sa.String(length=20), nullable=True))
    op.drop_column("purchase_orders", "receipt_tolerance_percent")


def downgrade():
    op.add_column("purchase_orders", sa.Column("receipt_tolerance_percent", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.drop_column("purchase_order_items", "uom")
    op.drop_column("purchase_order_items", "description")
    op.drop_index("ix_purchase_orders_location_id", table_name="purchase_orders")
    op.drop_index("ix_purchase_orders_department_id", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_location", "purchase_orders", type_="foreignkey")
    op.drop_constraint("fk_purchase_orders_department", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "location_id")
    op.drop_column("purchase_orders", "department_id")
