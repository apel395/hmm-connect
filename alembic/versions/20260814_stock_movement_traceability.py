"""add stock movement traceability

Revision ID: 20260814_stock_movement_traceability
Revises: 20260814_input_vat_posting
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_stock_movement_traceability"
down_revision = "20260814_input_vat_posting"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stock_movements", sa.Column("goods_receipt_item_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("purchase_order_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("purchase_order_item_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("business_unit_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("department_id", sa.Integer(), nullable=True))

    op.create_foreign_key("fk_stock_movements_goods_receipt_item", "stock_movements", "goods_receipt_items", ["goods_receipt_item_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_stock_movements_purchase_order", "stock_movements", "purchase_orders", ["purchase_order_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_stock_movements_purchase_order_item", "stock_movements", "purchase_order_items", ["purchase_order_item_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_stock_movements_business_unit", "stock_movements", "business_units", ["business_unit_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_stock_movements_location", "stock_movements", "locations", ["location_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_stock_movements_department", "stock_movements", "departments", ["department_id"], ["id"], ondelete="SET NULL")

    for column in ("goods_receipt_item_id", "purchase_order_id", "purchase_order_item_id", "business_unit_id", "location_id", "department_id"):
        op.create_index(f"ix_stock_movements_{column}", "stock_movements", [column], unique=False)

    op.execute("""
        UPDATE stock_movements sm
        SET purchase_order_id = gr.purchase_order_id,
            business_unit_id = gr.business_unit_id,
            location_id = gr.location_id,
            department_id = gr.department_id
        FROM goods_receipts gr
        WHERE sm.goods_receipt_id = gr.id
    """)


def downgrade():
    for column in ("department_id", "location_id", "business_unit_id", "purchase_order_item_id", "purchase_order_id", "goods_receipt_item_id"):
        op.drop_index(f"ix_stock_movements_{column}", table_name="stock_movements")
    op.drop_constraint("fk_stock_movements_department", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_location", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_business_unit", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_purchase_order_item", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_purchase_order", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_goods_receipt_item", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "department_id")
    op.drop_column("stock_movements", "location_id")
    op.drop_column("stock_movements", "business_unit_id")
    op.drop_column("stock_movements", "purchase_order_item_id")
    op.drop_column("stock_movements", "purchase_order_id")
    op.drop_column("stock_movements", "goods_receipt_item_id")
