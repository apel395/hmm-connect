"""Seed enforceable menu and action permissions.

Revision ID: 20260824_permission_enforcement
Revises: 20260824_finance_transaction_sync
"""

from alembic import op


revision = "20260824_permission_enforcement"
down_revision = "20260824_finance_transaction_sync"
branch_labels = None
depends_on = None


PERMISSIONS = [
    "dashboard.view", "approval.view", "approval.manage",
    "products.view", "products.manage", "suppliers.view", "suppliers.manage",
    "warehouse.view", "warehouse.manage",
    "pr.view", "pr.create", "pr.edit", "pr.submit", "pr.approve", "pr.convert", "pr.manage",
    "market_list.view", "market_list.create", "market_list.edit", "market_list.submit",
    "market_list.approve", "market_list.convert", "market_list.manage",
    "po.view", "po.create", "po.edit", "po.submit", "po.approve", "po.manage",
    "receiving.view", "receiving.manage", "inventory.view", "inventory.manage",
    "store_request.view", "store_request.manage", "stock_opname.view", "stock_opname.manage",
    "finance.view", "finance.manage", "ap.view", "ap.manage",
    "supplier_invoice.view", "supplier_invoice.create", "supplier_invoice.edit",
    "supplier_invoice.verify", "supplier_invoice.reject", "supplier_invoice.post",
    "supplier_invoice.void", "supplier_invoice.manage",
    "payment.view", "payment.manage", "journal.view", "journal.manage",
    "coa.view", "coa.manage", "reports.view", "reports.purchasing",
    "reports.inventory", "reports.finance", "reports.own", "audit.read",
    "admin.users.manage", "admin.roles.manage", "admin.settings.manage",
]

ROLE_GRANTS = {
    "GENERAL_MANAGER": [
        "dashboard.view", "approval.view", "approval.manage", "pr.view", "pr.approve",
        "market_list.view", "market_list.approve", "po.view", "po.approve",
        "receiving.view", "inventory.view", "finance.view", "reports.view",
    ],
    "PURCHASING": [
        "dashboard.view", "approval.view", "products.view", "suppliers.manage",
        "pr.view", "pr.convert", "market_list.view", "market_list.convert",
        "po.manage", "receiving.manage", "inventory.view", "reports.purchasing",
    ],
    "WAREHOUSE": [
        "dashboard.view", "approval.view", "warehouse.manage", "po.view",
        "receiving.manage", "inventory.manage", "store_request.manage",
        "stock_opname.manage", "reports.inventory",
    ],
    "FINANCE": [
        "dashboard.view", "approval.view", "finance.manage", "ap.manage",
        "supplier_invoice.manage", "payment.manage", "journal.manage", "coa.manage",
        "reports.finance", "pr.view", "market_list.view", "po.view", "receiving.view",
    ],
    "DEPARTMENT": [
        "dashboard.view", "approval.view", "pr.view", "pr.create", "pr.edit", "pr.submit",
        "market_list.view", "market_list.create", "market_list.edit", "market_list.submit",
        "store_request.manage", "reports.own",
    ],
    "AUDITOR": [
        "dashboard.view", "approval.view", "audit.read", "reports.view", "pr.view",
        "market_list.view", "po.view", "receiving.view", "inventory.view", "finance.view",
    ],
    "VIEWER": ["dashboard.view", "reports.view"],
}


def _quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    permission_values = ",\n".join(
        f"({_quoted(code)}, {_quoted(code.replace('.', ' ').replace('_', ' ').title())})"
        for code in PERMISSIONS
    )
    op.execute(
        f"""
        INSERT INTO permissions (code, description)
        VALUES {permission_values}
        ON CONFLICT (code) DO NOTHING
        """
    )

    grants = [
        (role_name, code)
        for role_name, codes in ROLE_GRANTS.items()
        for code in codes
    ]
    grant_values = ",\n".join(
        f"({_quoted(role_name)}, {_quoted(code)})"
        for role_name, code in grants
    )
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT role.id, permission.id
        FROM (VALUES {grant_values}) AS grant_map(role_name, permission_code)
        JOIN roles AS role ON role.name = grant_map.role_name
        JOIN permissions AS permission ON permission.code = grant_map.permission_code
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Permission assignments are administrator-managed data. A schema rollback
    # must not silently remove mappings that may have been edited after upgrade.
    pass
