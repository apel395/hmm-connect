"""Bank accounts and multi-source payment funding.

Revision ID: 20260809_bank_payment_funding
Revises: 20260808_amortization
"""
from alembic import op
import sqlalchemy as sa

revision = "20260809_bank_payment_funding"
down_revision = "20260808_amortization"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_name", sa.String(120), nullable=False),
        sa.Column("account_name", sa.String(180), nullable=False),
        sa.Column("account_number", sa.String(100), nullable=False),
        sa.Column("account_holder", sa.String(180), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"),
        sa.Column("business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
        sa.Column("coa_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("bank_name", "account_number", name="uq_bank_account_number"),
        sa.UniqueConstraint("coa_account_id", name="uq_bank_account_coa"),
    )
    op.create_index("ix_bank_accounts_bank_name", "bank_accounts", ["bank_name"])
    op.create_index("ix_bank_accounts_account_number", "bank_accounts", ["account_number"])
    op.create_index("ix_bank_accounts_business_unit_id", "bank_accounts", ["business_unit_id"])
    op.create_index("ix_bank_accounts_location_id", "bank_accounts", ["location_id"])

    op.create_table(
        "payment_funding_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_funding_lines_payment_id", "payment_funding_lines", ["payment_id"])
    op.create_index("ix_payment_funding_lines_bank_account_id", "payment_funding_lines", ["bank_account_id"])


def downgrade():
    op.drop_index("ix_payment_funding_lines_bank_account_id", table_name="payment_funding_lines")
    op.drop_index("ix_payment_funding_lines_payment_id", table_name="payment_funding_lines")
    op.drop_table("payment_funding_lines")
    op.drop_index("ix_bank_accounts_location_id", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_business_unit_id", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_account_number", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_bank_name", table_name="bank_accounts")
    op.drop_table("bank_accounts")
