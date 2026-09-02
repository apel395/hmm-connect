"""add point of sales transactions

Revision ID: 20260902_sales_transactions
Revises: 20260902_stock_adjustment
"""

from alembic import op
import sqlalchemy as sa

revision = "20260902_sales_transactions"
down_revision = "20260902_stock_adjustment"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sales_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column(
            "warehouse_id",
            sa.Integer(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "business_unit_id",
            sa.Integer(),
            sa.ForeignKey("business_units.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
        ),
        sa.Column("payment_method", sa.String(20)),
        sa.Column("payment_received", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("change_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("subtotal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("void_reason", sa.String(500)),
        sa.Column(
            "journal_entry_id",
            sa.Integer(),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("transaction_number"),
    )
    for column in (
        "transaction_number",
        "status",
        "sale_date",
        "warehouse_id",
        "created_by_id",
        "journal_entry_id",
    ):
        op.create_index(f"ix_sales_transactions_{column}", "sales_transactions", [column])
    op.create_table(
        "sales_transaction_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sales_transaction_id",
            sa.Integer(),
            sa.ForeignKey("sales_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer()),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("line_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("uom", sa.String(30), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "sales_transaction_id", "product_id", name="uq_sales_transaction_product"
        ),
    )
    op.create_index(
        "ix_sales_transaction_lines_sales_transaction_id",
        "sales_transaction_lines",
        ["sales_transaction_id"],
    )
    op.create_index(
        "ix_sales_transaction_lines_product_id", "sales_transaction_lines", ["product_id"]
    )

    op.execute(
        "INSERT INTO permissions (code, description) "
        "VALUES ('pos.view', 'View Point of Sale Transactions'), "
        "('pos.sell', 'Create and Post Point of Sale Transactions') "
        "ON CONFLICT (code) DO NOTHING"
    )
    for code in ("pos.view", "pos.sell"):
        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT role.id, permission.id
            FROM roles AS role
            JOIN permissions AS permission ON permission.code = '{code}'
            WHERE role.name IN ('SYSTEM_ADMINISTRATOR', 'WAREHOUSE', 'FINANCE', 'GENERAL_MANAGER', 'AUDITOR')
            ON CONFLICT DO NOTHING
            """
        )

    settings = [
        ("POS_CASH_ACCOUNT", "100-120-100", "Point of Sale cash received account"),
        ("POS_CARD_ACCOUNT", "100-110-117", "Point of Sale card payment account"),
        ("POS_TRANSFER_ACCOUNT", "100-110-118", "Point of Sale bank transfer account"),
        ("POS_SALES_REVENUE_ACCOUNT", "400-100-101", "Point of Sale sales revenue account"),
        ("POS_COGS_ACCOUNT", "500-100-999", "Point of Sale cost of goods sold account"),
        ("POS_TAX_PAYABLE_ACCOUNT", "200-400-106", "Point of Sale output VAT payable account"),
    ]
    for setting_key, account_number, description in settings:
        op.execute(
            f"""
            INSERT INTO accounting_settings (setting_key, account_id, description)
            SELECT '{setting_key}', coa.id, '{description}'
            FROM chart_of_accounts AS coa
            WHERE coa.account_number = '{account_number}'
            ON CONFLICT (setting_key) DO NOTHING
            """
        )


def downgrade():
    op.execute("DELETE FROM accounting_settings WHERE setting_key LIKE 'POS_%'")
    for code in ("pos.view", "pos.sell"):
        op.execute(
            "DELETE FROM role_permissions WHERE permission_id IN "
            f"(SELECT id FROM permissions WHERE code = '{code}')"
        )
        op.execute(f"DELETE FROM permissions WHERE code = '{code}'")
    op.drop_table("sales_transaction_lines")
    op.drop_table("sales_transactions")