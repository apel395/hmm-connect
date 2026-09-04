"""create opening_balances table (annual opening balance entries)

Revision ID: 20260904_opening_balances
Revises: 20260903_spt_1771
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_opening_balances"
down_revision = "20260903_spt_1771"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "opening_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance_type", sa.String(10), nullable=False, server_default="DEBIT"),
        sa.Column("description", sa.String(250), nullable=True),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_opening_balances_fiscal_year", "opening_balances", ["fiscal_year"])
    op.create_index("ix_opening_balances_account_id", "opening_balances", ["account_id"])
    op.create_index("ix_opening_balances_location_id", "opening_balances", ["location_id"])
    op.create_index("ix_opening_balances_journal_entry_id", "opening_balances", ["journal_entry_id"])


def downgrade():
    op.drop_index("ix_opening_balances_journal_entry_id", table_name="opening_balances")
    op.drop_index("ix_opening_balances_location_id", table_name="opening_balances")
    op.drop_index("ix_opening_balances_account_id", table_name="opening_balances")
    op.drop_index("ix_opening_balances_fiscal_year", table_name="opening_balances")
    op.drop_table("opening_balances")
