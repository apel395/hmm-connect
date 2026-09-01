"""Add missing LOCATION_2 (Pekanbaru) accounting settings.

Location 2 (002 Pekanbaru) is the only active location missing all of its
location-scoped accounting mappings. Without them, WAREHOUSE receiving at
Pekanbaru fails at POST because DirectCoaService.inventory_account() can
resolve neither a LOCATION_2_INVENTORY_* setting nor a product-level
inventory_account_id; supplier invoices at Pekanbaru also fail for lack of a
LOCATION_2_AP account.

Pekanbaru spans Central / Head Office / Project Catering / Hotel, so its
company-level accounts map to the "Hotel" chart rows (the food/beverage
inventory chart) with Petty Cash pointing at Head Office Catering.

Revision ID: 20260901_location2_accounting_settings
Revises: 20260901_po_created_by
"""
from alembic import op

revision = "20260901_location2_accounting_settings"
down_revision = "20260901_po_created_by"
branch_labels = None
depends_on = None

SETTINGS = {
    "LOCATION_2_AP": ("200-100-1", "Accounts Payable - Hotel (Pekanbaru)"),
    "LOCATION_2_AR": ("100-200-102", "Accounts Receivable - Hotel (Pekanbaru)"),
    "LOCATION_2_PETTY_CASH": ("100-100-107", "Petty Cash - Head Office Catering (Pekanbaru)"),
    "LOCATION_2_ACCRUAL": ("200-200-100", "Accrual - Hotel (Pekanbaru)"),
    "LOCATION_2_INVENTORY_FOOD": ("100-300-100", "Inventory Food - Hotel (Pekanbaru)"),
    "LOCATION_2_INVENTORY_BEVERAGE": ("100-300-500", "Inventory Beverage - Hotel (Pekanbaru)"),
    "LOCATION_2_INVENTORY_MATERIAL": ("100-300-700", "Inventory Material - Hotel (Pekanbaru)"),
}


def upgrade():
    bind = op.get_bind()
    for setting_key, (account_number, description) in SETTINGS.items():
        existing = bind.execute(
            op.text(
                "SELECT id FROM accounting_settings WHERE setting_key = :k"
            ),
            {"k": setting_key},
        ).fetchone()
        if existing:
            continue
        account = bind.execute(
            op.text("SELECT id FROM chart_of_accounts WHERE account_number = :n"),
            {"n": account_number},
        ).fetchone()
        if account is None:
            raise RuntimeError(f"COA {account_number} not found for {setting_key}")
        bind.execute(
            op.text(
                "INSERT INTO accounting_settings (setting_key, account_id, description) "
                "VALUES (:k, :a, :d)"
            ),
            {"k": setting_key, "a": account[0], "d": description},
        )


def downgrade():
    bind = op.get_bind()
    for setting_key in SETTINGS:
        bind.execute(
            op.text("DELETE FROM accounting_settings WHERE setting_key = :k"),
            {"k": setting_key},
        )
