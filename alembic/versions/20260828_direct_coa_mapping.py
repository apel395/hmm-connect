"""Add direct COA mappings and stock accounting snapshots.

Revision ID: 20260828_direct_coa_mapping
Revises: 20260828_supplier_invoice_location_repair
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_direct_coa_mapping"
down_revision = "20260828_supplier_invoice_location_repair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("payable_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_suppliers_payable_account_id_chart_of_accounts",
        "suppliers", "chart_of_accounts", ["payable_account_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_suppliers_payable_account_id", "suppliers", ["payable_account_id"])

    op.add_column("stock_movements", sa.Column("inventory_account_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("offset_account_id", sa.Integer(), nullable=True))
    op.add_column("stock_movements", sa.Column("journal_entry_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_stock_movements_inventory_account_id_chart_of_accounts",
        "stock_movements", "chart_of_accounts", ["inventory_account_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_stock_movements_offset_account_id_chart_of_accounts",
        "stock_movements", "chart_of_accounts", ["offset_account_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_stock_movements_journal_entry_id_journal_entries",
        "stock_movements", "journal_entries", ["journal_entry_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_stock_movements_journal_entry_id", "stock_movements", ["journal_entry_id"])

    # Global mapping only. No account number is guessed and historical journals
    # remain untouched. Finance configures this before posting a VAT invoice.
    op.execute(
        """
        INSERT INTO accounting_settings (setting_key, account_id, description)
        SELECT 'INPUT_VAT_ACCOUNT', id, 'Direct COA for supplier-invoice input VAT'
        FROM chart_of_accounts
        WHERE FALSE
        ON CONFLICT (setting_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_journal_entry_id", table_name="stock_movements")
    op.drop_constraint("fk_stock_movements_journal_entry_id_journal_entries", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_offset_account_id_chart_of_accounts", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_inventory_account_id_chart_of_accounts", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "journal_entry_id")
    op.drop_column("stock_movements", "offset_account_id")
    op.drop_column("stock_movements", "inventory_account_id")
    op.drop_index("ix_suppliers_payable_account_id", table_name="suppliers")
    op.drop_constraint("fk_suppliers_payable_account_id_chart_of_accounts", "suppliers", type_="foreignkey")
    op.drop_column("suppliers", "payable_account_id")
