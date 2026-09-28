"""Add persistent stock reconciliation adjustment requests.

Revision ID: 20260928_stock_reconciliation_requests
Revises: 20260921_async_journal_import
"""

from alembic import op
import sqlalchemy as sa

revision = "20260928_stock_reconciliation_requests"
down_revision = "20260921_async_journal_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_reconciliation_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_qty", sa.Numeric(14, 4), nullable=False),
        sa.Column("variance_qty", sa.Numeric(14, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name in ("fiscal_year", "product_id", "warehouse_id", "status"):
        op.create_index(f"ix_stock_reconciliation_requests_{name}", "stock_reconciliation_requests", [name])


def downgrade() -> None:
    op.drop_table("stock_reconciliation_requests")
