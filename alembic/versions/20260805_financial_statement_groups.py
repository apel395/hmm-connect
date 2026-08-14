"""add financial statement classification to chart of accounts

Revision ID: 20260805_financial_groups
Revises: 20260804_cash_flow_foundation
"""

from alembic import op
import sqlalchemy as sa


revision = "20260805_financial_groups"
down_revision = "20260804_cash_flow_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chart_of_accounts", sa.Column("financial_statement_group", sa.String(length=30), nullable=True))
    op.create_index("ix_chart_of_accounts_financial_statement_group", "chart_of_accounts", ["financial_statement_group"])


def downgrade():
    op.drop_index("ix_chart_of_accounts_financial_statement_group", table_name="chart_of_accounts")
    op.drop_column("chart_of_accounts", "financial_statement_group")
