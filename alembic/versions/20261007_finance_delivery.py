"""Service charge snapshots and explicit payment charges."""
from alembic import op
import sqlalchemy as sa

revision = "20261007_finance_delivery"
down_revision = "20261006_financial_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ar_invoice_layouts", sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), primary_key=True), sa.Column("configuration", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("products", sa.Column("service_charge_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("sales_transactions", sa.Column("service_charge_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("sales_transaction_lines", sa.Column("service_charge_rate", sa.Numeric(7, 4), nullable=False, server_default="0"))
    op.add_column("sales_transaction_lines", sa.Column("service_charge_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    for name in ("bank_charge_amount", "short_over_amount"):
        op.add_column("payments", sa.Column(name, sa.Numeric(18, 2), nullable=False, server_default="0"))
    for name in ("bank_charge_account_id", "short_over_account_id"):
        op.add_column("payments", sa.Column(name, sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=True))
    op.add_column("payments", sa.Column("difference_reason", sa.String(500), nullable=True))


def downgrade():
    op.drop_table("ar_invoice_layouts")
    for name in ("difference_reason", "short_over_account_id", "bank_charge_account_id", "short_over_amount", "bank_charge_amount"):
        op.drop_column("payments", name)
    for name in ("service_charge_amount", "service_charge_rate"):
        op.drop_column("sales_transaction_lines", name)
    op.drop_column("sales_transactions", "service_charge_amount")
    op.drop_column("products", "service_charge_rate")
