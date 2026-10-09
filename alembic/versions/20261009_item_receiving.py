"""Purchasing item scope, reference prices and Direct Use expense destinations."""
from alembic import op
import sqlalchemy as sa
revision = "20261009_item_receiving"
down_revision = "20261008_asset_item_master"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("catalog_type", sa.String(16), nullable=False, server_default="CATERING"))
    op.create_index("ix_products_catalog_type", "products", ["catalog_type"])
    op.add_column("products", sa.Column("reference_cost_method", sa.String(24), nullable=False, server_default="LAST_PURCHASE"))
    op.add_column("goods_receipt_items", sa.Column("expense_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_receipt_item_expense", "goods_receipt_items", "chart_of_accounts", ["expense_account_id"], ["id"])
    # All existing items remain in Catering. Hotel starts empty. Financial records are unchanged.


def downgrade():
    op.drop_constraint("fk_receipt_item_expense", "goods_receipt_items", type_="foreignkey")
    op.drop_column("goods_receipt_items", "expense_account_id")
    op.drop_column("products", "reference_cost_method")
    op.drop_index("ix_products_catalog_type", table_name="products")
    op.drop_column("products", "catalog_type")
