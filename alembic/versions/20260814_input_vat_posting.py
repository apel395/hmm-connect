"""add input VAT posting account

Revision ID: 20260814_input_vat_posting
Revises: 20260814_supplier_tax_profile
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_input_vat_posting"
down_revision = "20260814_supplier_tax_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounting_posting_rules",
        sa.Column(
            "input_vat_account_id",
            sa.Integer(),
            sa.ForeignKey("chart_of_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("accounting_posting_rules", "input_vat_account_id")
