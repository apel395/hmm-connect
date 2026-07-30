"""add purchase requisition expiry date

Revision ID: 20260730_pr_expiry
Revises: c84f91a2d7ab
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20260730_pr_expiry"
down_revision = "c84f91a2d7ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_requisitions",
        sa.Column("expiry_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_purchase_requisitions_expiry_date",
        "purchase_requisitions",
        ["expiry_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_requisitions_expiry_date",
        table_name="purchase_requisitions",
    )
    op.drop_column("purchase_requisitions", "expiry_date")