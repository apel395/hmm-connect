"""Persistent BUY Item Master link on the fixed asset register."""
from alembic import op
import sqlalchemy as sa
revision = "20261008_asset_item_master"
down_revision = "20261007_finance_delivery"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("fixed_assets", sa.Column("product_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_fixed_assets_product_id", "fixed_assets", "products", ["product_id"], ["id"])
    op.create_index("ix_fixed_assets_product_id", "fixed_assets", ["product_id"])
    # Existing explicit invoice item links need no inference or accounting changes.
    op.execute("UPDATE fixed_assets a SET product_id=l.product_id FROM supplier_invoice_lines l WHERE a.source_invoice_line_id=l.id AND l.product_id IS NOT NULL")

def downgrade():
    op.drop_index("ix_fixed_assets_product_id", table_name="fixed_assets")
    op.drop_constraint("fk_fixed_assets_product_id", "fixed_assets", type_="foreignkey")
    op.drop_column("fixed_assets", "product_id")
