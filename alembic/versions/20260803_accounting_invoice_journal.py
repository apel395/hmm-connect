"""add posting rules, supplier invoices, and journal review fields

Revision ID: 20260803_accounting_finance
Revises: 20260803_goods_receipt_status
"""
from alembic import op
import sqlalchemy as sa

revision = "20260803_accounting_finance"
down_revision = "20260803_goods_receipt_status"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    op.create_table("accounting_posting_rules",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("debit_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("credit_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("debit_account_id <> credit_account_id", name="ck_posting_rule_accounts_differ"))
    op.create_index("ix_accounting_posting_rules_event_type", "accounting_posting_rules", ["event_type"])
    op.create_index("uq_active_posting_rule_event", "accounting_posting_rules", ["event_type"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_table("supplier_invoices",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("internal_invoice_number", sa.String(50), nullable=False, unique=True),
        sa.Column("supplier_invoice_number", sa.String(100), nullable=False), sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False), sa.Column("received_date", sa.Date()), sa.Column("due_date", sa.Date()),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id", ondelete="SET NULL")),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipts.id", ondelete="SET NULL")),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"), sa.Column("subtotal", sa.Numeric(18,2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("tax_amount", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("withholding_tax_amount", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("total_amount", sa.Numeric(18,2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"), sa.Column("notes", sa.Text()),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="LIVE"), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("posted_at", sa.DateTime(timezone=True)), sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("supplier_id", "supplier_invoice_number", name="uq_supplier_invoice_number"))
    for column in ("internal_invoice_number","supplier_id","invoice_date","due_date","purchase_order_id","goods_receipt_id","status","source_type"):
        op.create_index(f"ix_supplier_invoices_{column}", "supplier_invoices", [column])
    op.create_table("supplier_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("supplier_invoice_id", sa.Integer(), sa.ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")), sa.Column("purchase_order_item_id", sa.Integer(), sa.ForeignKey("purchase_order_items.id", ondelete="SET NULL")),
        sa.Column("goods_receipt_item_id", sa.Integer(), sa.ForeignKey("goods_receipt_items.id", ondelete="SET NULL")), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18,4), nullable=False), sa.Column("uom", sa.String(20)), sa.Column("unit_price", sa.Numeric(18,2), nullable=False),
        sa.Column("line_amount", sa.Numeric(18,2), nullable=False), sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id")),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")), sa.Column("notes", sa.Text()))
    op.create_index("ix_supplier_invoice_lines_supplier_invoice_id", "supplier_invoice_lines", ["supplier_invoice_id"])
    if "journal_entries" not in existing_tables:
        op.create_table("journal_entries",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("journal_number", sa.String(50), nullable=False, unique=True),
            sa.Column("posting_date", sa.Date(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="POSTED"),
            sa.Column("document_type", sa.String(50)), sa.Column("document_number", sa.String(100)),
            sa.Column("reference_type", sa.String(50), nullable=False), sa.Column("reference_id", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text()), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("posted_at", sa.DateTime(timezone=True)),
            sa.Column("voided_at", sa.DateTime(timezone=True)), sa.Column("fiscal_year", sa.Integer()), sa.Column("fiscal_period", sa.Integer()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
        for column in ("journal_number","posting_date","status","document_type","document_number","reference_type","reference_id","fiscal_year","fiscal_period"):
            op.create_index(f"ix_journal_entries_{column}", "journal_entries", [column])
    else:
        op.add_column("journal_entries", sa.Column("voided_at", sa.DateTime(timezone=True)))
    if "journal_lines" not in existing_tables:
        op.create_table("journal_lines",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
            sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
            sa.Column("debit", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("credit", sa.Numeric(18,2), nullable=False, server_default="0"),
            sa.Column("description", sa.Text()), sa.Column("line_number", sa.Integer()),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="SET NULL")))
        op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
        op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])
    else:
        op.add_column("journal_lines", sa.Column("line_number", sa.Integer()))
        op.add_column("journal_lines", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")))
        op.add_column("journal_lines", sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")))
        op.add_column("journal_lines", sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="SET NULL")))

def downgrade():
    # Journal tables may have predated this migration; retain them on downgrade.
    for column in ("supplier_id","location_id","department_id","line_number"): op.drop_column("journal_lines", column)
    op.drop_column("journal_entries", "voided_at")
    op.drop_table("supplier_invoice_lines"); op.drop_table("supplier_invoices"); op.drop_table("accounting_posting_rules")
