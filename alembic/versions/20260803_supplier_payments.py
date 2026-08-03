"""extend supplier payments and invoice balances

Revision ID: 20260803_supplier_payments
Revises: 20260803_accounting_finance
"""
from alembic import op
import sqlalchemy as sa
revision="20260803_supplier_payments";down_revision="20260803_accounting_finance";branch_labels=None;depends_on=None
def upgrade():
    op.alter_column("payments","account_payable_id",existing_type=sa.Integer(),nullable=True)
    for col in [sa.Column("supplier_id",sa.Integer(),sa.ForeignKey("suppliers.id")),sa.Column("payment_account_id",sa.Integer(),sa.ForeignKey("chart_of_accounts.id")),sa.Column("currency",sa.String(3),nullable=False,server_default="IDR"),sa.Column("cheque_number",sa.String(100)),sa.Column("notes",sa.Text()),sa.Column("source_type",sa.String(30),nullable=False,server_default="LIVE"),sa.Column("approved_by_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("posted_by_id",sa.Integer(),sa.ForeignKey("users.id")),sa.Column("journal_entry_id",sa.Integer(),sa.ForeignKey("journal_entries.id")),sa.Column("approved_at",sa.DateTime(timezone=True)),sa.Column("posted_at",sa.DateTime(timezone=True)),sa.Column("voided_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]:op.add_column("payments",col)
    op.create_index("ix_payments_supplier_id","payments",["supplier_id"])
    op.execute("UPDATE payments SET status='POSTED' WHERE status='PAID'")
    op.create_table("payment_allocations",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("payment_id",sa.Integer(),sa.ForeignKey("payments.id",ondelete="CASCADE"),nullable=False),sa.Column("supplier_invoice_id",sa.Integer(),sa.ForeignKey("supplier_invoices.id"),nullable=False),sa.Column("allocated_amount",sa.Numeric(18,2),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("payment_id","supplier_invoice_id",name="uq_payment_invoice_allocation"))
    op.create_index("ix_payment_allocations_payment_id","payment_allocations",["payment_id"]);op.create_index("ix_payment_allocations_supplier_invoice_id","payment_allocations",["supplier_invoice_id"])
    op.add_column("supplier_invoices",sa.Column("paid_amount",sa.Numeric(18,2),nullable=False,server_default="0"));op.add_column("supplier_invoices",sa.Column("balance_amount",sa.Numeric(18,2),nullable=False,server_default="0"));op.add_column("supplier_invoices",sa.Column("payment_status",sa.String(20),nullable=False,server_default="UNPAID"));op.execute("UPDATE supplier_invoices SET balance_amount=total_amount")
def downgrade():
    for c in ("payment_status","balance_amount","paid_amount"):op.drop_column("supplier_invoices",c)
    op.drop_table("payment_allocations")
    for c in ("updated_at","voided_at","posted_at","approved_at","journal_entry_id","posted_by_id","approved_by_id","source_type","notes","cheque_number","currency","payment_account_id","supplier_id"):op.drop_column("payments",c)
