"""add explicit market item flag

Revision ID: 20260818_market_item_flag
Revises: 20260816_market_list
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_market_item_flag"
down_revision = "20260816_market_list"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("is_market_item", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_products_is_market_item", "products", ["is_market_item"], unique=False)

    # Preserve the current Market List behavior on deployment: FOOD and BEVERAGE
    # were previously treated as market items. Finance/Admin can then explicitly
    # opt individual products in or out from Item Master.
    op.execute(
        "UPDATE products SET is_market_item = TRUE WHERE group_code IN ('1', '2')"
    )


def downgrade():
    op.drop_index("ix_products_is_market_item", table_name="products")
    op.drop_column("products", "is_market_item")
