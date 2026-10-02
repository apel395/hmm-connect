"""Add selling item service, organization scope and tax profile.

Revision ID: 20261002_sell_item_profile
Revises: 20260928_stock_recon
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_sell_item_profile"
down_revision = "20260928_stock_recon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("sales_service_name", sa.String(120), nullable=True))
    op.add_column("products", sa.Column("sales_business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id"), nullable=True))
    op.add_column("products", sa.Column("sales_location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True))
    for name in ("pbjt_rate", "sales_ppn_rate", "pph23_rate"):
        op.add_column("products", sa.Column(name, sa.Numeric(7, 4), nullable=False, server_default="0"))


def downgrade() -> None:
    for name in ("pph23_rate", "sales_ppn_rate", "pbjt_rate", "sales_location_id", "sales_business_unit_id", "sales_service_name"):
        op.drop_column("products", name)
