"""Support direct goods receipts.

Revision ID: 20260807_direct_receiving
Revises: 20260810_fixed_assets
"""
from alembic import op
import sqlalchemy as sa

revision = "20260807_direct_receiving"
down_revision = "20260810_fixed_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("goods_receipts", "purchase_order_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("goods_receipts", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_goods_receipts_supplier_id", "goods_receipts", "suppliers", ["supplier_id"], ["id"], ondelete="SET NULL")
    op.alter_column("goods_receipt_items", "purchase_order_item_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("goods_receipt_items", "purchase_order_item_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("fk_goods_receipts_supplier_id", "goods_receipts", type_="foreignkey")
    op.drop_column("goods_receipts", "supplier_id")
    op.alter_column("goods_receipts", "purchase_order_id", existing_type=sa.Integer(), nullable=False)
