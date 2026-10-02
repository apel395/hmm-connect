"""Register invoice-backed assets before depreciation setup.

Revision ID: 20261002_invoice_asset_register
Revises: 20261002_sell_item_profile
"""
from alembic import op
import sqlalchemy as sa

revision = "20261002_invoice_asset_register"
down_revision = "20261002_sell_item_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fixed_assets", sa.Column(
        "source_invoice_line_id", sa.Integer(),
        sa.ForeignKey("supplier_invoice_lines.id"), nullable=True,
    ))
    op.create_index(
        "ix_fixed_assets_source_invoice_line_id", "fixed_assets", ["source_invoice_line_id"], unique=True,
    )
    for column in (
        "asset_category_id", "useful_life_months",
        "accumulated_depreciation_account_id", "depreciation_expense_account_id",
    ):
        op.alter_column("fixed_assets", column, existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Pending source assets have no category/depreciation mapping. Require
    # completion before restoring the old NOT NULL schema.
    connection = op.get_bind()
    pending = connection.execute(sa.text(
        "SELECT count(*) FROM fixed_assets WHERE asset_category_id IS NULL "
        "OR useful_life_months IS NULL OR accumulated_depreciation_account_id IS NULL "
        "OR depreciation_expense_account_id IS NULL"
    )).scalar_one()
    if pending:
        raise RuntimeError("Complete pending fixed asset setup before downgrading")
    for column in (
        "asset_category_id", "useful_life_months",
        "accumulated_depreciation_account_id", "depreciation_expense_account_id",
    ):
        op.alter_column("fixed_assets", column, existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_fixed_assets_source_invoice_line_id", table_name="fixed_assets")
    op.drop_column("fixed_assets", "source_invoice_line_id")
