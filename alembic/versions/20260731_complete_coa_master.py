"""complete COA master fields

Revision ID: 20260731_complete_coa
Revises: 20260731_purchasing_docs
"""
from alembic import op
import sqlalchemy as sa

revision = "20260731_complete_coa"
down_revision = "20260731_purchasing_docs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chart_of_accounts", sa.Column("normal_balance", sa.String(length=10), nullable=True))
    op.add_column("chart_of_accounts", sa.Column("description", sa.String(length=500), nullable=True))
    op.execute("UPDATE chart_of_accounts SET normal_balance = CASE WHEN account_type IN ('ASSET', 'EXPENSE') THEN 'DEBIT' ELSE 'CREDIT' END")
    op.alter_column("chart_of_accounts", "normal_balance", nullable=False)


def downgrade():
    op.drop_column("chart_of_accounts", "description")
    op.drop_column("chart_of_accounts", "normal_balance")
