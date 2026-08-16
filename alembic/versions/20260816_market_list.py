"""add market list module

Revision ID: 20260816_market_list
Revises: 20260814_stock_movement_traceability
"""
from alembic import op
import sqlalchemy as sa

revision = "20260816_market_list"
down_revision = "20260814_stock_movement_traceability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_lists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ml_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT"),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="LIVE"),
        sa.Column("external_reference", sa.String(length=100), nullable=True),
        sa.Column("business_unit_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("ml_number"),
    )
    op.create_index("ix_market_lists_ml_number", "market_lists", ["ml_number"], unique=True)
    for column in ("business_unit_id", "location_id", "department_id", "requested_by_id"):
        op.create_index(f"ix_market_lists_{column}", "market_lists", [column], unique=False)

    op.create_table(
        "market_list_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("market_list_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("estimated_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["market_list_id"], ["market_lists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_market_list_items_market_list_id", "market_list_items", ["market_list_id"], unique=False)
    op.create_index("ix_market_list_items_product_id", "market_list_items", ["product_id"], unique=False)

    op.add_column("purchase_orders", sa.Column("market_list_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_orders_market_list", "purchase_orders", "market_lists",
        ["market_list_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_purchase_orders_market_list_id", "purchase_orders", ["market_list_id"], unique=False)

    op.add_column("purchase_order_items", sa.Column("market_list_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_purchase_order_items_market_list_item", "purchase_order_items", "market_list_items",
        ["market_list_item_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_purchase_order_items_market_list_item_id", "purchase_order_items", ["market_list_item_id"], unique=False)


def downgrade():
    op.drop_index("ix_purchase_order_items_market_list_item_id", table_name="purchase_order_items")
    op.drop_constraint("fk_purchase_order_items_market_list_item", "purchase_order_items", type_="foreignkey")
    op.drop_column("purchase_order_items", "market_list_item_id")
    op.drop_index("ix_purchase_orders_market_list_id", table_name="purchase_orders")
    op.drop_constraint("fk_purchase_orders_market_list", "purchase_orders", type_="foreignkey")
    op.drop_column("purchase_orders", "market_list_id")
    op.drop_index("ix_market_list_items_product_id", table_name="market_list_items")
    op.drop_index("ix_market_list_items_market_list_id", table_name="market_list_items")
    op.drop_table("market_list_items")
    for column in ("requested_by_id", "department_id", "location_id", "business_unit_id"):
        op.drop_index(f"ix_market_lists_{column}", table_name="market_lists")
    op.drop_index("ix_market_lists_ml_number", table_name="market_lists")
    op.drop_table("market_lists")
