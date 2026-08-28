"""Add location-aware direct COA mappings.

Revision ID: 20260828_location_direct_coa
Revises: 20260828_location_repair_v2
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_location_direct_coa"
down_revision = "20260828_location_repair_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_location_coa_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inventory_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="RESTRICT")),
        sa.Column("purchase_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="RESTRICT")),
        sa.Column("cogs_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("product_id", "location_id", name="uq_product_location_coa"),
    )
    op.create_index("ix_product_location_coa_product", "product_location_coa_mappings", ["product_id"])
    op.create_index("ix_product_location_coa_location", "product_location_coa_mappings", ["location_id"])

    op.create_table(
        "supplier_location_coa_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payable_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("supplier_id", "location_id", name="uq_supplier_location_coa"),
    )
    op.create_index("ix_supplier_location_coa_supplier", "supplier_location_coa_mappings", ["supplier_id"])
    op.create_index("ix_supplier_location_coa_location", "supplier_location_coa_mappings", ["location_id"])

    op.create_table(
        "location_tax_coa_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("input_vat_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="RESTRICT"), nullable=False),
    )
    op.create_index("ix_location_tax_coa_location", "location_tax_coa_mappings", ["location_id"], unique=True)


def downgrade() -> None:
    op.drop_table("location_tax_coa_mappings")
    op.drop_table("supplier_location_coa_mappings")
    op.drop_table("product_location_coa_mappings")
