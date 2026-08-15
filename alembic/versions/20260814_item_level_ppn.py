"""Add item-level PPN columns across purchasing documents.

Revision ID: 20260814_item_level_ppn
Revises: 20260810_supplier_adjustments, 20260810_fixed_assets
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_item_level_ppn"
down_revision = ("20260810_supplier_adjustments", "20260810_fixed_assets")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchase_requisitions", sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("purchase_requisitions", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))

    for table in ("purchase_requisition_items", "purchase_order_items", "goods_receipt_items", "supplier_invoice_lines"):
        op.add_column(table, sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
        op.add_column(table, sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))

    op.add_column("goods_receipts", sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("goods_receipts", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("goods_receipts", sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))

    # Preserve legacy totals as pre-tax subtotal until item-level tax is explicitly selected.
    op.execute("UPDATE purchase_requisitions SET subtotal = total_amount WHERE subtotal = 0")


def downgrade():
    for table in ("supplier_invoice_lines", "goods_receipt_items", "purchase_order_items", "purchase_requisition_items"):
        op.drop_column(table, "tax_amount")
        op.drop_column(table, "tax_rate")
        op.drop_column(table, "is_taxable")

    op.drop_column("goods_receipts", "total_amount")
    op.drop_column("goods_receipts", "tax_amount")
    op.drop_column("goods_receipts", "subtotal")
    op.drop_column("purchase_requisitions", "tax_amount")
    op.drop_column("purchase_requisitions", "subtotal")
