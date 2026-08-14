"""cash flow account classification and bank transfers

Revision ID: 20260804_cash_flow_foundation
Revises: 20260803_historical_fields
"""
from alembic import op
import sqlalchemy as sa

revision="20260804_cash_flow_foundation"
down_revision="20260803_historical_fields"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("chart_of_accounts",sa.Column("account_subtype",sa.String(20),nullable=False,server_default="OTHER"))
    op.create_index("ix_chart_of_accounts_account_subtype","chart_of_accounts",["account_subtype"])
    op.add_column("journal_lines",sa.Column("cash_flow_category",sa.String(20)))
    op.add_column("journal_lines",sa.Column("cash_flow_direction",sa.String(20)))
    op.create_index("ix_journal_lines_cash_flow_category","journal_lines",["cash_flow_category"])
    op.create_table("bank_transfers",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("transfer_number",sa.String(50),nullable=False,unique=True),sa.Column("transfer_date",sa.Date(),nullable=False),
        sa.Column("source_account_id",sa.Integer(),sa.ForeignKey("chart_of_accounts.id"),nullable=False),sa.Column("destination_account_id",sa.Integer(),sa.ForeignKey("chart_of_accounts.id"),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("currency",sa.String(3),nullable=False,server_default="IDR"),sa.Column("reference_number",sa.String(100)),sa.Column("notes",sa.Text()),
        sa.Column("status",sa.String(20),nullable=False,server_default="DRAFT"),sa.Column("journal_entry_id",sa.Integer(),sa.ForeignKey("journal_entries.id",ondelete="SET NULL"),unique=True),
        sa.Column("created_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("posted_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("posted_at",sa.DateTime(timezone=True)))
    op.create_index("ix_bank_transfers_transfer_number","bank_transfers",["transfer_number"]);op.create_index("ix_bank_transfers_transfer_date","bank_transfers",["transfer_date"]);op.create_index("ix_bank_transfers_status","bank_transfers",["status"]);op.create_index("ix_bank_transfers_source_account_id","bank_transfers",["source_account_id"]);op.create_index("ix_bank_transfers_destination_account_id","bank_transfers",["destination_account_id"])

def downgrade():
    op.drop_table("bank_transfers");op.drop_index("ix_journal_lines_cash_flow_category",table_name="journal_lines");op.drop_column("journal_lines","cash_flow_direction");op.drop_column("journal_lines","cash_flow_category");op.drop_index("ix_chart_of_accounts_account_subtype",table_name="chart_of_accounts");op.drop_column("chart_of_accounts","account_subtype")
