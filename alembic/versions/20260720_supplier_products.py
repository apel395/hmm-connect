"""add supplier product master

Revision ID: 20260720_supplier_products
Revises: 20260720_approval_workflows
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_supplier_products"
down_revision: Union[str, Sequence[str], None] = "20260720_approval_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("supplier_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("supplier_id", "product_id", name="uq_supplier_products_supplier_product"),
    )
    op.create_index("ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"])
    op.create_index("ix_supplier_products_product_id", "supplier_products", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_supplier_products_product_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_table("supplier_products")
