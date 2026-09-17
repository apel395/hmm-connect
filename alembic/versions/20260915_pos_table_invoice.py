"""Add POS table and direct invoice metadata.

Revision ID: 20260915_pos_table_invoice
Revises: 20260915_coa_cleanup
"""

from alembic import op
import sqlalchemy as sa

revision = "20260915_pos_table_invoice"
down_revision = "20260915_coa_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_transactions",
        sa.Column("transaction_type", sa.String(length=20), nullable=False, server_default="POS"),
    )
    op.add_column(
        "sales_transactions",
        sa.Column("table_number", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "sales_transactions",
        sa.Column("queue_number", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_sales_transactions_transaction_type",
        "sales_transactions",
        ["transaction_type"],
    )
    op.create_index(
        "ix_sales_transactions_table_number",
        "sales_transactions",
        ["table_number"],
    )
    op.create_index(
        "ix_sales_transactions_queue_number",
        "sales_transactions",
        ["queue_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_transactions_queue_number", table_name="sales_transactions")
    op.drop_index("ix_sales_transactions_table_number", table_name="sales_transactions")
    op.drop_index("ix_sales_transactions_transaction_type", table_name="sales_transactions")
    op.drop_column("sales_transactions", "queue_number")
    op.drop_column("sales_transactions", "table_number")
    op.drop_column("sales_transactions", "transaction_type")
