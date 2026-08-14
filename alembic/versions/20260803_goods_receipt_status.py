"""add goods receipt posting status

Revision ID: 20260803_goods_receipt_status
Revises: 20260801_po_creation
"""
from alembic import op
import sqlalchemy as sa


revision = "20260803_goods_receipt_status"
down_revision = "20260801_po_creation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "goods_receipts",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="POSTED"),
    )
    op.alter_column("goods_receipts", "status", server_default=None)


def downgrade():
    op.drop_column("goods_receipts", "status")
