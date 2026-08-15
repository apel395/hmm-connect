"""add item master tax profile

Revision ID: 20260814_product_tax_profile
Revises: 20260814_purchase_order_subtotal
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_product_tax_profile"
down_revision = "20260814_purchase_order_subtotal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("tax_category", sa.String(length=30), nullable=False, server_default="REVIEW_REQUIRED"))
    op.add_column("products", sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("products", sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("tax_reason", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("tax_reference", sa.String(length=255), nullable=True))

    # Existing products are intentionally not guessed. Finance must classify them.
    op.execute("UPDATE products SET tax_category = 'REVIEW_REQUIRED', is_taxable = false, tax_rate = 0")


def downgrade():
    op.drop_column("products", "tax_reference")
    op.drop_column("products", "tax_reason")
    op.drop_column("products", "tax_rate")
    op.drop_column("products", "is_taxable")
    op.drop_column("products", "tax_category")
